import time

import constants
import googleapiclient.discovery
from flask import flash
from utils.google_cloud_general import GoogleCloudGeneral


class GoogleCloudCompute(GoogleCloudGeneral):

    def __init__(self, project) -> None:
        super().__init__(project)
        self.compute = googleapiclient.discovery.build('compute', 'v1')

    def validate_networking(self):
        existing_nets = [net['name'] for net in self.compute.networks().list(
            project=self.project).execute()['items']]

        if constants.NETWORK_NAME not in existing_nets:
            self.create_network(constants.NETWORK_NAME)
            self.create_subnet(constants.REGION, constants.NETWORK_NAME)
            self.create_firewalls(constants.NETWORK_NAME)

    def create_network(self, network_name):
        flash("Creating new network for GWAS")
        print("Creating new network for GWAS")
        req_body = {
            'name': network_name,
            'autoCreateSubnetworks': False,
            'routingConfig': {'routingMode': 'GLOBAL'}
        }
        operation = self.compute.networks().insert(
            project=self.project, body=req_body).execute()
        self.wait_for_operation(operation['name'])

    def create_subnet(self, region, network_name):
        flash("Creating new subnetwork for GWAS")
        print("Creating new subnetwork for GWAS")
        network_url = ''
        for net in self.compute.networks().list(project=self.project).execute()['items']:
            if net['name'] == network_name:
                network_url = net['selfLink']

        req_body = {
            'name': constants.SUBNET_NAME,
            'network': network_url,
            'ipCidrRange': '10.0.0.0/28'

        }
        operation = self.compute.subnetworks().insert(
            project=self.project, region=region, body=req_body).execute()
        self.wait_for_regionOperation(region, operation['name'])

    def create_firewalls(self, network_name):
        flash("Creating new firewalls for GWAS")
        print("Creating new firewalls for GWAS")
        network_url = ''
        for net in self.compute.networks().list(project=self.project).execute()['items']:
            if net['name'] == network_name:
                network_url = net['selfLink']

        firewall_body = {
            'name': network_name + '-vm-ingress',
            'network': network_url,
            'sourceRanges': ['0.0.0.0/0'],
            'allowed': [{'ports': ['8000-8999', '22'], 'IPProtocol': 'tcp'}]
        }
        operation = self.compute.firewalls().insert(
            project=self.project, body=firewall_body).execute()
        self.wait_for_operation(operation['name'])

    def validate_instance(self, instance):
        existing_instances = self.list_instances(constants.ZONE)

        if not existing_instances or instance not in existing_instances:
            self.create_instance(constants.ZONE, instance)

        self.start_instance(constants.ZONE, instance)
        time.sleep(5)

        return self.get_vm_external_ip_address(constants.ZONE, instance)

    def create_instance(self, zone, name):
        instance_body = {
            "name": name,
            "machineType": "zones/{}/machineTypes/{}".format(zone, constants.MACHINE_TYPE),
            "networkInterfaces": [{
                'network': 'projects/{}/global/networks/{}'.format(self.project, constants.NETWORK_NAME),
                'subnetwork': 'regions/{}/subnetworks/{}'.format(constants.REGION, constants.SUBNET_NAME),
                'accessConfigs': [
                    {'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}
                ]
            }],
            "disks": [{
                "boot": True,
                "initializeParams": {
                    "sourceImage": "projects/debian-cloud/global/images/family/debian-9"
                }
            }]
        }
        operation = self.compute.instances().insert(
            project=self.project, zone=zone, body=instance_body).execute()

        self.wait_for_zoneOperation(zone, operation['name'])
        time.sleep(10)
        self.transfer_file_to_instance(name, 'startup-script.sh', '~/')

        self.execute_shell_script_on_instance(name, ['chmod u+x startup-script.sh', './startup-script.sh'])

    def start_instance(self, zone, instance):
        operation = self.compute.instances().start(
            project=self.project, zone=zone, instance=instance).execute()
        self.wait_for_zoneOperation(zone, operation['name'])

    def stop_instance(self, zone, instance):
        operation = self.compute.instances().stop(
            project=self.project, zone=zone, instance=instance).execute()
        self.wait_for_zoneOperation(zone, operation['name'])

    def list_instances(self, zone):
        result = self.compute.instances().list(
            project=self.project, zone=zone).execute()
        return [instance['name'] for instance in result['items']] if 'items' in result else None

    def delete_instance(self, zone, name):
        return self.compute.instances().delete(project=self.project, zone=zone, instance=name).execute()

    def wait_for_operation(self, operation):
        print("Waiting for operation to finish...")
        while True:
            result = self.compute.globalOperations().get(
                project=self.project, operation=operation).execute()

            if result['status'] == 'DONE':
                print("done.")
                if "error" in result:
                    raise Exception(result['error'])
                return result

            time.sleep(1)

    def wait_for_zoneOperation(self, zone, operation):
        print("Waiting for operation to finish...")
        while True:
            result = self.compute.zoneOperations().get(project=self.project, zone=zone,
                                                       operation=operation).execute()

            if result['status'] == 'DONE':
                print("done.")
                if "error" in result:
                    raise Exception(result['error'])
                return result

            time.sleep(1)

    def wait_for_regionOperation(self, region, operation):
        print("Waiting for operation to finish...")
        while True:
            result = self.compute.regionOperations().get(
                project=self.project, region=region, operation=operation).execute()

            if result['status'] == 'DONE':
                print("done.")
                if "error" in result:
                    raise Exception(result['error'])
                return result

            time.sleep(1)

    def get_vm_external_ip_address(self, zone, instance):
        print("Getting the IP address for VM instance ", instance)
        response = self.compute.instances().get(
            project=self.project, zone=zone, instance=instance).execute()
        return response['networkInterfaces'][0]['accessConfigs'][0]['natIP']

    def update_ip_addresses_on_vm(self, ip_addresses, instance, role):
        cmds = [
            'cd ~/secure-gwas; rm log/*; rm cache/*'
        ]
        for (k, v) in ip_addresses:
            cmds.append(
                'sed -i "s|^{k}.*$|{k} {v}|g" ~/secure-gwas/par/test.par.{role}.txt'.format(k=k, v=v, role=role))
        self.execute_shell_script_on_instance(instance, cmds)

    def run_data_sharing(self, instance, role):
        cmds = []
        if str(role) != "3":
            cmds = [
                'cd ~/secure-gwas/code',
                'bin/DataSharingClient {role} ../par/test.par.{role}.txt'.format(
                    role=role),
                'echo completed DataSharing',
            ]
        else:
            cmds = [
                'cd ~/secure-gwas/code',
                'bin/DataSharingClient {role} ../par/test.par.{role}.txt ../test_data/'.format(
                    role=role),
                'echo completed'
            ]

        self.execute_shell_script_on_instance(instance, cmds)

    def run_gwas_client(self, instance, role):
        cmds = []
        if str(role) != "3":
            cmds = [
                'cd ~/secure-gwas/code',
                'bin/GwasClient {role} ../par/test.par.{role}.txt'.format(
                    role=role),
                'echo completed GwasClient',
            ]
            self.execute_shell_script_on_instance(instance, cmds)
