import os
import subprocess
from time import sleep

import googleapiclient.discovery as googleapi
import ipaddr
from src.utils import constants
from tenacity import retry
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed


class GoogleCloudCompute:
    """
    Class to handle interactions with Google Cloud Compute Engine
    """

    def __init__(self, project: str) -> None:
        self.project: str = project
        self.compute = googleapi.build("compute", "v1")

    def setup_networking(self, doc_ref_dict: dict, role: str) -> None:
        gcp_projects: list = [constants.SERVER_GCP_PROJECT]
        gcp_projects.extend(
            doc_ref_dict["personal_parameters"][participant]["GCP_PROJECT"]["value"]
            for participant in doc_ref_dict["participants"]
        )

        self.create_network()
        self.remove_conflicting_peerings(gcp_projects)
        self.remove_conflicting_subnets(gcp_projects)
        self.create_subnet(role)
        self.create_peerings(gcp_projects)

    def create_network(self, network_name: str = constants.NETWORK_NAME) -> None:
        networks: list = self.compute.networks().list(project=self.project).execute()["items"]
        network_names: list[str] = [net["name"] for net in networks]

        if network_name not in network_names:
            print(f"Creating new network {network_name}")
            req_body = {
                "name": network_name,
                "autoCreateSubnetworks": False,
                "routingConfig": {"routingMode": "GLOBAL"},
            }
            operation = self.compute.networks().insert(project=self.project, body=req_body).execute()
            self.wait_for_operation(operation["name"])

            self.create_firewall(network_name)

    def create_firewall(self, network_name: str = constants.NETWORK_NAME) -> None:
        print(f"Creating new firewalls for network {network_name}")
        network_url: str = ""
        for net in self.compute.networks().list(project=self.project).execute()["items"]:
            if net["name"] == network_name:
                network_url = net["selfLink"]

        firewall_body: dict = {
            "name": f"{network_name}-vm-ingress",
            "network": network_url,
            "targetTags": [constants.INSTANCE_NAME_ROOT],
            "sourceRanges": constants.BROAD_VM_SOURCE_IP_RANGES if "broad-cho-priv" in self.project else ["0.0.0.0/0"],
            "allowed": [{"ports": ["8000-8999", "22"], "IPProtocol": "tcp"}],
        }

        operation = self.compute.firewalls().insert(project=self.project, body=firewall_body).execute()
        self.wait_for_operation(operation["name"])

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    def remove_conflicting_peerings(self, gcp_projects: list) -> None:
        # a peering is conflicting if it connects to a project that is not in the current study
        network_info = self.compute.networks().get(project=self.project, network=constants.NETWORK_NAME).execute()
        peerings = [peer["name"].replace("peering-", "") for peer in network_info.get("peerings", [])]

        for other_project in peerings:
            if other_project not in gcp_projects:
                print(f"Deleting peering from {self.project} to {other_project}")
                body = {"name": f"peering-{other_project}"}
                self.compute.networks().removePeering(
                    project=self.project, network=constants.NETWORK_NAME, body=body
                ).execute()
                sleep(2)

    def remove_conflicting_subnets(self, gcp_projects: list) -> None:
        # a subnet is conflicting if it has an IpCidrRange that does not match the expected ranges based on the roles of participants in the study
        subnets = (
            self.compute.subnetworks().list(project=self.project, region=constants.SERVER_REGION).execute()["items"]
        )
        ip_ranges = [f"10.0.{i}.0/24" for i in range(3) if gcp_projects[i] == self.project]
        for subnet in subnets:
            if constants.NETWORK_NAME in subnet["network"] and subnet["ipCidrRange"] not in ip_ranges:
                n1 = ipaddr.IPNetwork(subnet["ipCidrRange"])
                if any(n1.overlaps(ipaddr.IPNetwork(n2)) for n2 in ip_ranges):
                    self.delete_subnet(subnet)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(30))
    def delete_subnet(self, subnet: dict) -> None:
        for instance in self.list_instances(constants.SERVER_ZONE, subnetwork=subnet["selfLink"]):
            self.delete_instance(instance)

        print(f"Deleting subnet {subnet['name']}")
        self.compute.subnetworks().delete(
            project=self.project,
            region=constants.SERVER_REGION,
            subnetwork=subnet["name"],
        ).execute()

        # wait for the subnet to be deleted
        for _ in range(30):
            subnets = (
                self.compute.subnetworks()
                .list(project=self.project, region=constants.SERVER_REGION)
                .execute()["items"]
            )
            if subnet["name"] not in [sub["name"] for sub in subnets]:
                return
            sleep(2)

        print(f"Failure to delete subnet {subnet['name']}")
        raise RuntimeError(f"Failure to delete subnet {subnet['name']}")

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(30))
    def create_subnet(self, role: str, region: str = constants.SERVER_REGION) -> None:
        # create subnet if it doesn't already exist
        subnet_name = constants.SUBNET_NAME + role
        subnets = (
            self.compute.subnetworks().list(project=self.project, region=constants.SERVER_REGION).execute()["items"]
        )
        subnet_names = [subnet["name"] for subnet in subnets]
        if subnet_name not in subnet_names:
            print(f"Creating new subnetwork {subnet_name}")
            network_url = ""
            for net in self.compute.networks().list(project=self.project).execute()["items"]:
                if net["name"] == constants.NETWORK_NAME:
                    network_url = net["selfLink"]

            req_body = {
                "name": subnet_name,
                "network": network_url,
                "ipCidrRange": f"10.0.{role}.0/24",
            }
            operation = self.compute.subnetworks().insert(project=self.project, region=region, body=req_body).execute()
            self.wait_for_region_operation(region, operation["name"])

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(30))
    def create_peerings(self, gcp_projects: list) -> None:
        # create peerings if they don't already exist
        network_info = self.compute.networks().get(project=self.project, network=constants.NETWORK_NAME).execute()
        peerings = [peer["name"].replace("peering-", "") for peer in network_info.get("peerings", [])]
        other_projects = [p for p in gcp_projects if p != self.project]
        for other_project in other_projects:
            if other_project not in peerings:
                print("Creating peering from", self.project, "to", other_project)
                body = {
                    "networkPeering": {
                        "name": f"peering-{other_project}",
                        "network": f"https://www.googleapis.com/compute/v1/projects/{other_project}/global/networks/{constants.NETWORK_NAME}",
                        "exchangeSubnetRoutes": True,
                    }
                }

                self.compute.networks().addPeering(
                    project=self.project, network=constants.NETWORK_NAME, body=body
                ).execute()

    def setup_sfgwas_instance(self, instance_name: str, metadata: dict = dict()) -> str:
        print("Setting up SFGWAS instance")
        if instance_name not in self.list_instances():
            self.create_instance(
                instance_name, "0", metadata=metadata, startup_script="sfgwas", num_cpus=8, boot_disk_size=50
            )
        return self.get_vm_external_ip_address(instance_name)

    def setup_instance(
        self,
        zone: str,
        name: str,
        role: str,
        metadata: dict,
        num_cpus: int = 4,
        boot_disk_size: int = 10,
        startup_script: str = "web",
        delete: bool = True,
    ) -> str:
        existing_instances = self.list_instances(zone=zone)

        if name in existing_instances and delete:
            self.delete_instance(name, zone)

        if name not in existing_instances:
            self.create_instance(name, role, zone, num_cpus, boot_disk_size, metadata, startup_script=startup_script)

        return self.get_vm_external_ip_address(name, zone)

    def create_instance(
        self,
        name: str,
        role: str,
        zone: str = constants.SERVER_ZONE,
        num_cpus: int = 0,
        boot_disk_size: int = 10,
        metadata: dict = dict(),
        startup_script: str = "web",
    ) -> None:
        print("Creating VM instance with name", name)

        image_response = self.compute.images().getFromFamily(project="debian-cloud", family="debian-11").execute()
        # image_response = self.compute.images().getFromFamily(project="ubuntu-os-cloud", family="ubuntu-2110").execute()
        source_disk_image = image_response["selfLink"]
        machine_type = f"zones/{zone}/machineTypes/e2-medium"
        if num_cpus:
            machine_type = f"zones/{zone}/machineTypes/e2-highmem-{num_cpus}"

        instance_body = {
            "name": name,
            "machineType": machine_type,
            "networkInterfaces": [
                {
                    "network": f"projects/{self.project}/global/networks/{constants.NETWORK_NAME}",
                    "subnetwork": f"regions/{constants.SERVER_REGION}/subnetworks/{constants.SUBNET_NAME + role}",
                    "networkIP": f"10.0.{role}.10",
                    "accessConfigs": [
                        {
                            "type": "ONE_TO_ONE_NAT",
                            "name": "External NAT",
                        }  # This is necessary to give the VM access to the internet, which it needs to do things like download the git repos.
                        # See (https://cloud.google.com/compute/docs/reference/rest/v1/instances) for more information.  If it helps, the external IP address is ephemeral.
                    ],
                }
            ],
            "disks": [
                {
                    "boot": True,
                    "autoDelete": True,
                    "initializeParams": {"sourceImage": source_disk_image},
                    "diskSizeGb": boot_disk_size,
                }
            ],
            "serviceAccounts": [
                {
                    "email": "default",
                    "scopes": [
                        "https://www.googleapis.com/auth/devstorage.read_write",
                        "https://www.googleapis.com/auth/logging.write",
                        "https://www.googleapis.com/auth/pubsub",
                        "https://www.googleapis.com/auth/datastore",
                    ],
                }
            ],
            "tags": {"items": [constants.INSTANCE_NAME_ROOT]},
        }

        if startup_script:
            startup_script = open(
                os.path.join(os.path.dirname(__file__), f"../../vm_scripts/startup-script-{startup_script}.sh"),
                "r",
            ).read()

            metadata_config = {
                "items": [
                    {"key": "startup-script", "value": startup_script},
                    {"key": "enable-oslogin", "value": True},
                ]
            }
            if metadata:
                metadata_config["items"].append(metadata)
            instance_body["metadata"] = metadata_config

        operation = self.compute.instances().insert(project=self.project, zone=zone, body=instance_body).execute()
        self.wait_for_zone_operation(zone, operation["name"])

    def stop_instance(self, zone: str, instance: str) -> None:
        print("Stopping VM instance with name ", instance)

        operation = self.compute.instances().stop(project=self.project, zone=zone, instance=instance).execute()
        self.wait_for_zone_operation(zone, operation["name"])

    def list_instances(self, zone: str = constants.SERVER_ZONE, subnetwork: str = "") -> list[str]:
        result = self.compute.instances().list(project=self.project, zone=zone).execute()
        return [
            instance["name"]
            for instance in result.get("items", [])
            if subnetwork in instance["networkInterfaces"][0]["subnetwork"]
        ]

    def delete_instance(self, name: str, zone: str = constants.SERVER_ZONE) -> None:
        print("Deleting VM instance with name ", name)
        operation = self.compute.instances().delete(project=self.project, zone=zone, instance=name).execute()
        self.wait_for_zone_operation(zone, operation["name"])

    def wait_for_operation(self, operation: str) -> dict[str, str]:
        print("Waiting for operation to finish...", end="")
        while True:
            result = self.compute.globalOperations().get(project=self.project, operation=operation).execute()

            if result["status"] == "DONE":
                return self.return_result_or_error(result)
            sleep(1)

    def wait_for_zone_operation(self, zone: str, operation: str) -> dict[str, str]:
        print("Waiting for operation to finish...", end="")
        while True:
            result = self.compute.zoneOperations().get(project=self.project, zone=zone, operation=operation).execute()

            if result["status"] == "DONE":
                return self.return_result_or_error(result)
            sleep(1)

    def wait_for_region_operation(self, region: str, operation: str) -> dict[str, str]:
        print("Waiting for operation to finish...", end="")
        while True:
            result: dict[str, str] = (
                self.compute.regionOperations().get(project=self.project, region=region, operation=operation).execute()
            )

            if result["status"] == "DONE":
                return self.return_result_or_error(result)
            sleep(1)

    def return_result_or_error(self, result: dict[str, str]) -> dict[str, str]:
        print("done.")
        if "error" in result:
            raise RuntimeError(result["error"])
        return result

    def get_vm_external_ip_address(self, instance: str, zone: str = constants.SERVER_ZONE) -> str:
        print("Getting the IP address for VM instance", instance)
        response = self.compute.instances().get(project=self.project, zone=zone, instance=instance).execute()
        return response["networkInterfaces"][0]["accessConfigs"][0]["natIP"]

    def get_service_account_for_vm(self, zone: str, instance: str) -> str:
        print("Getting the service account for VM instance", instance)
        response = self.compute.instances().get(project=self.project, zone=zone, instance=instance).execute()
        return response["serviceAccounts"][0]["email"]


def run_command(instance_name: str, cmd: str) -> None:
    command = f"gcloud compute ssh {instance_name} --project {constants.SERVER_GCP_PROJECT} --zone={constants.SERVER_ZONE} --command '{cmd}'"
    if subprocess.run(command, shell=True).returncode != 0:
        print(f"Failed to perform command {command}")
        exit(1)


def run_ssh_command(ip_address: str, cmd: str) -> None:
    command = f"ssh -o StrictHostKeyChecking=accept-new smendels@{ip_address} -t '{cmd}'"
    if subprocess.run(command, shell=True).returncode != 0:
        print(f"Failed to perform command {command}")
        exit(1)
