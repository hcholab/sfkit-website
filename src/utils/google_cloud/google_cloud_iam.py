from src.utils import constants
import googleapiclient.discovery as googleapi


class GoogleCloudIAM:
    def __init__(self) -> None:
        self.service = googleapi.build("cloudresourcemanager", "v1")
        self.project = constants.SERVER_GCP_PROJECT

    def get_policy(self, version: int = 1):
        """Gets IAM policy for a project."""

        return (
            self.service.projects()
            .getIamPolicy(
                resource=self.project,
                body={"options": {"requestedPolicyVersion": version}},
            )
            .execute()
        )

    def modify_policy_add_member(self, policy, role, member):
        """Adds a new member to a role binding."""

        no_role = True
        for binding in policy["bindings"]:
            if binding["role"] == role:
                no_role = False
                binding["members"].append(member)
                break
        if no_role:
            binding = {"role": role, "members": [member]}
            policy["bindings"].append(binding)
        return policy

    def set_policy(self, policy):
        """Sets IAM policy for a project."""

        policy = self.service.projects().setIamPolicy(resource=self.project, body={"policy": policy}).execute()
        return policy

    def give_cloud_build_view_permissions(self, user):
        """Gives Cloud Build Viewer permissions to a user."""
        print(f"Giving Cloud Build Viewer permissions to user: {user}")

        policy = self.get_policy()
        policy = self.modify_policy_add_member(policy, "roles/cloudbuild.builds.viewer", f"user:{user}")
        policy = self.modify_policy_add_member(policy, "roles/logging.viewer", f"user:{user}")
        self.set_policy(policy)

    def test_permissions(self, project_id) -> bool:
        """Tests IAM permissions of the caller"""
        print(f"Testing IAM permissions for project: {project_id}")

        desired_permissions = [
            "compute.disks.create",
            "compute.firewallPolicies.create",
            "compute.firewallPolicies.get",
            "compute.instances.create",
            "compute.instances.delete",
            "compute.instances.get",
            "compute.instances.list",
            "compute.instances.setMetadata",
            "compute.instances.setServiceAccount",
            "compute.instances.stop",
            "compute.networks.access",
            "compute.networks.addPeering",
            "compute.networks.create",
            "compute.networks.get",
            "compute.networks.list",
            "compute.networks.removePeering",
            "compute.networks.updatePolicy",
            "compute.subnetworks.create",
            "compute.subnetworks.delete",
            "compute.subnetworks.list",
            "compute.subnetworks.use",
            "compute.subnetworks.useExternalIp",
            "iam.serviceAccounts.actAs",
        ]

        permissions = {"permissions": desired_permissions}

        returnedPermissions = (
            self.service.projects().testIamPermissions(resource=project_id, body=permissions).execute()
        )

        print(f'Returned permissions: {returnedPermissions.get("permissions")}')

        return returnedPermissions.get("permissions") == desired_permissions
