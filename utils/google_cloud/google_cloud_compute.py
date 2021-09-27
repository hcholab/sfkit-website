import os
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

    def validate_instance(self, instance, role):
        existing_instances = self.list_instances(constants.ZONE)

        if not existing_instances or instance not in existing_instances:
            self.create_instance(constants.ZONE, instance, role)
            self.wait_for_startup_script(role)

        self.start_instance(constants.ZONE, instance)
        time.sleep(5)

        return self.get_vm_external_ip_address(constants.ZONE, instance)

    def create_instance(self, zone, name, role):
        print("Creating VM instance with name ", name)

        image_response = self.compute.images().getFromFamily(
            project='debian-cloud', family='debian-11').execute()
        source_disk_image = image_response['selfLink']

        # Configure the machine
        # machine_type = "zones/%s/machineTypes/e2-medium" % zone
        machine_type = "zones/%s/machineTypes/c2-standard-4" % zone
        startup_script = open(
            os.path.join(
                os.path.dirname(__file__), '../../startup-script.sh'), 'r').read()

        instance_body = {
            "name": name,
            "machineType": machine_type,
            "networkInterfaces": [{
                'network': 'projects/{}/global/networks/{}'.format(self.project, constants.NETWORK_NAME),
                'subnetwork': 'regions/{}/subnetworks/{}'.format(constants.REGION, constants.SUBNET_NAME),
                'networkIP': '10.0.0.{}'.format(str(int(role) + 10)),
                'accessConfigs': [
                    {'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}
                ]
            }],
            "disks": [{
                "boot": True,
                "autoDelete": True,
                "initializeParams": {
                    "sourceImage": source_disk_image
                }
            }],
            # Allow the instance to access cloud storage and logging.
            # Logging access necessary for the startup-script to work.
            "serviceAccounts": [{
                'email': 'default',
                'scopes': [
                    'https://www.googleapis.com/auth/devstorage.read_write',
                    'https://www.googleapis.com/auth/logging.write',
                    'https://www.googleapis.com/auth/pubsub'
                ]
            }],
            'metadata': {
                'items': [{
                    # Startup script is automatically executed by the
                    # instance upon startup.
                    'key': 'startup-script',
                    'value': startup_script
                }]
            }
        }
        operation = self.compute.instances().insert(
            project=self.project, zone=zone, body=instance_body).execute()

        self.wait_for_zoneOperation(zone, operation['name'])
        
    def wait_for_startup_script(self, role):
        from concurrent.futures import TimeoutError
        from google.cloud import pubsub_v1
        import socket

        project_id = "broad-cho-priv2"
        topic_id = "secure-gwas" + role
        subscription_id = socket.gethostname() + "-subscribing-to-" + topic_id  
        timeout = 1200 # seconds

        project_path = f"projects/{project_id}"
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(project_id, topic_id)
        subscriber = pubsub_v1.SubscriberClient()
        subscription_path = subscriber.subscription_path(project_id, subscription_id)
        
        topic_list = publisher.list_topics(request={"project": project_path})
        topic_list = list(map(lambda topic: str(topic).split('"')[1], topic_list))
        if topic_path not in topic_list:
            print(f"Creating topic {topic_path}")
            publisher.create_topic(name=topic_path)

        subscription_list = subscriber.list_subscriptions(request={"project": project_path})
        subscription_list = list(map(lambda topic: str(topic).split('"')[1], subscription_list))
        if subscription_path not in subscription_list:
            print(f"Creating subscription {subscription_path}")
            subscriber.create_subscription(name = subscription_path, topic = topic_path)

        prevTime = time.time()
        def callback(message: pubsub_v1.subscriber.message.Message) -> None:
            print(f"Received {message}.")
            message.ack()
            streaming_pull_future.cancel()
            streaming_pull_future.result()
            print(f"The startup took {time.time() - prevTime} seconds.")

        streaming_pull_future = subscriber.subscribe(subscription_path, callback=callback)
        print(f"Listening for messages on topic {topic_path}...\n")

        with subscriber:
            try:
                streaming_pull_future.result(timeout=timeout)
            except TimeoutError:
                streaming_pull_future.cancel()
                streaming_pull_future.result()

    def start_instance(self, zone, instance):
        print("Starting VM instance with name ", instance)
        operation = self.compute.instances().start(
            project=self.project, zone=zone, instance=instance).execute()
        self.wait_for_zoneOperation(zone, operation['name'])

    def stop_instance(self, zone, instance):
        print("Stopping VM instance with name ", instance)
        operation = self.compute.instances().stop(
            project=self.project, zone=zone, instance=instance).execute()
        self.wait_for_zoneOperation(zone, operation['name'])

    def list_instances(self, zone):
        result = self.compute.instances().list(
            project=self.project, zone=zone).execute()
        return [instance['name'] for instance in result['items']] if 'items' in result else None

    def delete_instance(self, zone, name):
        print("Deleting VM isntance with name ", name)
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
        from google.cloud import pubsub_v1
        import socket

        project_id = "broad-cho-priv2"

        topic_id = "web-server"

        publisher = pubsub_v1.PublisherClient()
        project_path = f"projects/{project_id}"
        topic_path = publisher.topic_path(project_id, topic_id)

        topic_list = publisher.list_topics(request={"project": project_path})
        topic_list = list(map(lambda topic: str(topic).split('"')[1], topic_list))
        if topic_path not in topic_list:
            print(f"Creating topic {topic_path}")
            publisher.create_topic(name=topic_path)

        data = " ".join(ip_addresses).encode("utf-8")
        future = publisher.publish(topic_path, data)
        print(future.result())
        print(f"Finished publishing message(s) to {topic_path}")


    def run_data_sharing(self, instance, role):
        cmds = []
        if str(role) != "3":
            cmds = [
                'cd /home/secure-gwas/code',
                'sudo bin/DataSharingClient {role} ../par/test.par.{role}.txt'.format(
                    role=role),
                'echo completed DataSharing',
            ]
        else:
            cmds = [
                'cd /home/secure-gwas/code',
                'sudo bin/DataSharingClient {role} ../par/test.par.{role}.txt ../test_data/'.format(
                    role=role),
                'echo completed'
            ]

        self.execute_shell_script_on_instance(instance, cmds)

    def run_gwas_client(self, instance, role):
        cmds = []
        if str(role) != "3":
            cmds = [
                'cd /home/secure-gwas/code',
                'sudo bin/GwasClient {role} ../par/test.par.{role}.txt'.format(
                    role=role),
                'echo completed GwasClient',
            ]
            self.execute_shell_script_on_instance(instance, cmds)
