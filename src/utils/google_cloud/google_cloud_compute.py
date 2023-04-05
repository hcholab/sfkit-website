import os
from time import sleep

import googleapiclient.discovery as googleapi
import ipaddr
from tenacity import retry
from tenacity.stop import stop_after_attempt
from tenacity.wait import wait_fixed

from src.utils import constants


class GoogleCloudCompute:
    """
    Class to handle interactions with Google Cloud Compute Engine
    """

    def __init__(self, study_title: str, gcp_project: str) -> None:
        self.gcp_project: str = gcp_project
        self.study_title: str = study_title.replace(" ", "").lower()
        self.network_name = f"{constants.NETWORK_NAME_ROOT}-{study_title}"
        self.firewall_name = f"{self.network_name}-vm-ingress"
        self.compute = googleapi.build("compute", "v1")

    def delete_everything(self) -> None:
        self.remove_conflicting_peerings()

        for instance in self.list_instances():
            if instance[:-1] == create_instance_name(self.study_title, ""):
                self.delete_instance(instance)

        try:
            firewalls: list = self.compute.firewalls().list(project=self.gcp_project).execute()["items"]
        except Exception as e:
            print(f"Error getting firewalls: {e}")
            firewalls = []
        firewall_names: list[str] = [firewall["name"] for firewall in firewalls]
        for firewall_name in firewall_names:
            if firewall_name == self.firewall_name:
                self.delete_firewall(firewall_name)

        try:
            subnets: list = (
                self.compute.subnetworks()
                .list(project=self.gcp_project, region=constants.SERVER_REGION)
                .execute()["items"]
            )
        except Exception as e:
            print(f"Error getting subnets: {e}")
            subnets = []
        for subnet in subnets:
            if subnet["name"][:-1] == create_subnet_name(self.network_name, ""):
                self.delete_subnet(subnet)

        self.delete_network()

    def setup_networking(self, doc_ref_dict: dict, role: str) -> None:
        print(f"Setting up networking for role {role}...")
        gcp_projects: list = [constants.SERVER_GCP_PROJECT]
        gcp_projects.extend(
            doc_ref_dict["personal_parameters"][participant]["GCP_PROJECT"]["value"]
            for participant in doc_ref_dict["participants"]
        )

        self.create_network_if_it_does_not_already_exist(doc_ref_dict)
        self.remove_conflicting_peerings(gcp_projects)
        self.remove_conflicting_subnets(gcp_projects)
        self.create_subnet(role)
        if doc_ref_dict["setup_configuration"] == "website":
            self.create_peerings(gcp_projects)

    def create_network_if_it_does_not_already_exist(self, doc_ref_dict: dict) -> None:
        networks: list = self.compute.networks().list(project=self.gcp_project).execute()["items"]
        network_names: list[str] = [net["name"] for net in networks]

        if self.network_name not in network_names:
            print(f"Creating new network {self.network_name}")
            req_body = {
                "name": self.network_name,
                "autoCreateSubnetworks": False,
                "routingConfig": {"routingMode": "GLOBAL"},
            }
            operation = self.compute.networks().insert(project=self.gcp_project, body=req_body).execute()
            self.wait_for_operation(operation["name"])

            self.create_firewall(doc_ref_dict)
        else:
            print(f"Network {self.network_name} already exists")

    def delete_network(self) -> None:
        try:
            networks: list = self.compute.networks().list(project=self.gcp_project).execute()["items"]
        except Exception as e:
            print(f"Error getting networks: {e}")
            networks = []
        network_names: list[str] = [net["name"] for net in networks]

        if self.network_name in network_names:
            print(f"Deleting network {self.network_name}")
            operation = self.compute.networks().delete(project=self.gcp_project, network=self.network_name).execute()
            self.wait_for_operation(operation["name"])

    def create_firewall(self, doc_ref_dict) -> None:
        print(f"Creating new firewalls for network {self.network_name}")
        network_url: str = ""
        for net in self.compute.networks().list(project=self.gcp_project).execute()["items"]:
            if net["name"] == self.network_name:
                network_url = net["selfLink"]

        source_ranges: list = constants.SOURCE_IP_RANGES
        for participant in doc_ref_dict["participants"]:
            ip = doc_ref_dict["personal_parameters"][participant]["IP_ADDRESS"]["value"]
            if ip != "":
                source_ranges.append(ip)

        firewall_body: dict = {
            "name": self.firewall_name,
            "network": network_url,
            "targetTags": [constants.INSTANCE_NAME_ROOT],
            "sourceRanges": source_ranges,
            "allowed": [{"ports": ["8000-12000", "22"], "IPProtocol": "tcp"}],
        }

        operation = self.compute.firewalls().insert(project=self.gcp_project, body=firewall_body).execute()
        self.wait_for_operation(operation["name"])

    def delete_firewall(self, firewall_name: str) -> None:
        print(f"Deleting firewall {firewall_name}")
        operation = self.compute.firewalls().delete(project=self.gcp_project, firewall=firewall_name).execute()
        self.wait_for_operation(operation["name"])

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(10))
    def remove_conflicting_peerings(self, gcp_projects: list = list()) -> bool:
        # a peering is conflicting if it connects to a project that is not in the current study
        try:
            network_info = self.compute.networks().get(project=self.gcp_project, network=self.network_name).execute()
        except Exception as e:  # googleapi.HttpError:
            # print(f"Error getting network info: {e}")
            return False
        peerings = [peer["name"].split("peering-")[1] for peer in network_info.get("peerings", [])]

        for other_project in peerings:
            if other_project not in gcp_projects:
                print(f"Deleting peering called {self.study_title}peering-{other_project}")
                body = {"name": f"{self.study_title}peering-{other_project}"}
                self.compute.networks().removePeering(
                    project=self.gcp_project, network=self.network_name, body=body
                ).execute()
                sleep(2)
        return True

    def remove_conflicting_subnets(self, gcp_projects: list) -> None:
        # a subnet is conflicting if it has an IpCidrRange that does not match the expected ranges based on the roles of participants in the study
        subnets = (
            self.compute.subnetworks()
            .list(project=self.gcp_project, region=constants.SERVER_REGION)
            .execute()["items"]
        )
        ip_ranges = [f"10.0.{i}.0/24" for i in range(3) if gcp_projects[i] == self.gcp_project]
        for subnet in subnets:
            if self.network_name in subnet["network"] and subnet["ipCidrRange"] not in ip_ranges:
                n1 = ipaddr.IPNetwork(subnet["ipCidrRange"])
                if any(n1.overlaps(ipaddr.IPNetwork(n2)) for n2 in ip_ranges):
                    self.delete_subnet(subnet)

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(30))
    def delete_subnet(self, subnet: dict) -> None:
        for instance in self.list_instances(constants.SERVER_ZONE, subnetwork=subnet["selfLink"]):
            self.delete_instance(instance)

        print(f"Deleting subnet {subnet['name']}")
        self.compute.subnetworks().delete(
            project=self.gcp_project,
            region=constants.SERVER_REGION,
            subnetwork=subnet["name"],
        ).execute()

        # wait for the subnet to be deleted
        for _ in range(30):
            subnets = (
                self.compute.subnetworks()
                .list(project=self.gcp_project, region=constants.SERVER_REGION)
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
        subnet_name = create_subnet_name(self.network_name, role)
        subnets = (
            self.compute.subnetworks()
            .list(project=self.gcp_project, region=constants.SERVER_REGION)
            .execute()["items"]
        )
        subnet_names = [subnet["name"] for subnet in subnets]
        if subnet_name not in subnet_names:
            print(f"Creating new subnetwork {subnet_name}")
            network_url = ""
            for net in self.compute.networks().list(project=self.gcp_project).execute()["items"]:
                if net["name"] == self.network_name:
                    network_url = net["selfLink"]

            req_body = {
                "name": subnet_name,
                "network": network_url,
                "ipCidrRange": f"10.0.{role}.0/24",
            }
            operation = (
                self.compute.subnetworks().insert(project=self.gcp_project, region=region, body=req_body).execute()
            )
            self.wait_for_region_operation(region, operation["name"])

    @retry(stop=stop_after_attempt(3), wait=wait_fixed(30))
    def create_peerings(self, gcp_projects: list) -> None:
        # create peerings if they don't already exist
        network_info = self.compute.networks().get(project=self.gcp_project, network=self.network_name).execute()
        peerings = [peer["name"].split("peering-")[1] for peer in network_info.get("peerings", [])]
        other_projects = [p for p in gcp_projects if p != self.gcp_project]
        for other_project in other_projects:
            if other_project not in peerings:
                print(f"Creating peering called {self.study_title}peering-{other_project}")
                body = {
                    "networkPeering": {
                        "name": f"{self.study_title}peering-{other_project}",
                        "network": f"https://www.googleapis.com/compute/v1/projects/{other_project}/global/networks/{self.network_name}",
                        "exchangeSubnetRoutes": True,
                    }
                }

                self.compute.networks().addPeering(
                    project=self.gcp_project, network=self.network_name, body=body
                ).execute()

    def setup_instance(
        self,
        name: str,
        role: str,
        metadata: list,
        num_cpus: int = 16,
        boot_disk_size: int = 10,
        delete: bool = True,
    ) -> str:
        if name in self.list_instances() and delete:
            self.delete_instance(name)
            print("Waiting for instance to be deleted...")

            max_wait = 60
            while name in self.list_instances() and max_wait > 0:
                sleep(2)
                max_wait -= 1

        if name not in self.list_instances():
            self.create_instance(
                name=name,
                role=role,
                num_cpus=num_cpus,
                boot_disk_size=boot_disk_size,
                metadata=metadata,
            )

        return self.get_vm_external_ip_address(name)

    def create_instance(
        self,
        name: str,
        role: str,
        zone: str = constants.SERVER_ZONE,
        num_cpus: int = 16,
        boot_disk_size: int = 10,
        metadata: list = list(),
    ) -> None:
        print(f"Creating VM instance with name {name} in project {self.gcp_project}")

        image_response = self.compute.images().getFromFamily(project="debian-cloud", family="debian-11").execute()
        # image_response = self.compute.images().getFromFamily(project="ubuntu-os-cloud", family="ubuntu-2110").execute()
        source_disk_image = image_response["selfLink"]
        if num_cpus <= 16:
            machine_type = f"zones/{zone}/machineTypes/e2-highmem-{num_cpus}"
        else:
            machine_type = f"zones/{zone}/machineTypes/n2-highmem-{num_cpus}"

        instance_body = {
            "name": name,
            "machineType": machine_type,
            "networkInterfaces": [
                {
                    "network": f"projects/{self.gcp_project}/global/networks/{self.network_name}",
                    "subnetwork": f"regions/{constants.SERVER_REGION}/subnetworks/{self.network_name}-subnet{role}",
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
                        "https://www.googleapis.com/auth/monitoring.write",
                        "https://www.googleapis.com/auth/datastore",
                    ],
                }
            ],
            "tags": {"items": [constants.INSTANCE_NAME_ROOT]},
        }

        startup_script = open(
            os.path.join(os.path.dirname(__file__), "../../vm_scripts/startup-script.sh"),
            "r",
        ).read()

        metadata_config = {
            "items": [
                {"key": "startup-script", "value": startup_script},
                {"key": "enable-oslogin", "value": True},
            ]
        }
        if metadata:
            metadata_config["items"] += metadata
        instance_body["metadata"] = metadata_config

        operation = self.compute.instances().insert(project=self.gcp_project, zone=zone, body=instance_body).execute()
        self.wait_for_zone_operation(zone, operation["name"])

    def stop_instance(self, name: str, zone: str = constants.SERVER_ZONE) -> None:
        print(f"Stopping VM instance with name {name}...")
        operation = self.compute.instances().stop(project=self.gcp_project, zone=zone, instance=name).execute()
        self.wait_for_zone_operation(zone, operation["name"])

    def list_instances(self, zone: str = constants.SERVER_ZONE, subnetwork: str = "") -> list[str]:
        try:
            result = self.compute.instances().list(project=self.gcp_project, zone=zone).execute()
        except Exception as e:
            print("Error listing instances:", e)
            return []
        return [
            instance["name"]
            for instance in result.get("items", [])
            if subnetwork in instance["networkInterfaces"][0]["subnetwork"]
        ]

    def delete_instance(self, name: str, zone: str = constants.SERVER_ZONE) -> None:
        print(f"Deleting VM instance with name {name}...")
        operation = self.compute.instances().delete(project=self.gcp_project, zone=zone, instance=name).execute()
        self.wait_for_zone_operation(zone, operation["name"])

    def wait_for_operation(self, operation: str) -> dict[str, str]:
        print("Waiting for operation to finish...", end="")
        while True:
            result = self.compute.globalOperations().get(project=self.gcp_project, operation=operation).execute()

            if result["status"] == "DONE":
                return self.return_result_or_error(result)
            sleep(1)

    def wait_for_zone_operation(self, zone: str, operation: str) -> dict[str, str]:
        print("Waiting for operation to finish...", end="")
        while True:
            result = (
                self.compute.zoneOperations().get(project=self.gcp_project, zone=zone, operation=operation).execute()
            )

            if result["status"] == "DONE":
                return self.return_result_or_error(result)
            sleep(1)

    def wait_for_region_operation(self, region: str, operation: str) -> dict[str, str]:
        print("Waiting for operation to finish...", end="")
        while True:
            result: dict[str, str] = (
                self.compute.regionOperations()
                .get(project=self.gcp_project, region=region, operation=operation)
                .execute()
            )

            if result["status"] == "DONE":
                return self.return_result_or_error(result)
            sleep(1)

    def return_result_or_error(self, result: dict[str, str]) -> dict[str, str]:
        print("done.")
        if "error" in result:
            if "RESOURCE_NOT_FOUND" in str(result):
                return result
            else:
                raise RuntimeError(result["error"])
        return result

    def get_vm_external_ip_address(self, instance: str, zone: str = constants.SERVER_ZONE) -> str:
        print("Getting the IP address for VM instance", instance)
        response = self.compute.instances().get(project=self.gcp_project, zone=zone, instance=instance).execute()
        return response["networkInterfaces"][0]["accessConfigs"][0]["natIP"]


def create_instance_name(study_title: str, role: str) -> str:
    return f"{study_title.replace(' ', '').lower()}-{constants.INSTANCE_NAME_ROOT}{role}"


def create_subnet_name(network_name: str, role: str) -> str:
    return f"{network_name}-subnet{role}"
