import googleapiclient.discovery as googleapi

from src.utils import constants


class GoogleCloudIAM:
    """
    Class to handle interactions with the Google Cloud IAM API.
    """

    def __init__(self) -> None:
        self.service = googleapi.build("cloudresourcemanager", "v1")
        self.project = constants.SERVER_GCP_PROJECT

    def get_policy(self, version: int = 1) -> dict:
        """Gets IAM policy for a project."""

        return (
            self.service.projects()
            .getIamPolicy(
                resource=self.project,
                body={"options": {"requestedPolicyVersion": version}},
            )
            .execute()
        )

    def modify_policy_add_member(self, policy: dict, role: str, member: str) -> dict:
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

    def set_policy(self, policy: dict) -> dict:
        """Sets IAM policy for a project."""

        policy = self.service.projects().setIamPolicy(resource=self.project, body={"policy": policy}).execute()
        return policy

    def give_minimal_required_gcp_permissions(self, user: str, member_type: str = "user") -> None:
        """Gives Cloud Build Viewer permissions to a user."""
        print(f"Giving Cloud Build Viewer permissions to user: {user}")

        policy = self.get_policy()
        policy = self.modify_policy_add_member(policy, "roles/cloudbuild.builds.viewer", f"{member_type}:{user}")
        policy = self.modify_policy_add_member(policy, "roles/logging.viewer", f"{member_type}:{user}")
        policy = self.modify_policy_add_member(policy, "roles/firebase.viewer", f"{member_type}:{user}")
        self.set_policy(policy)

    def test_permissions(self, project_id: str) -> bool:
        """Tests IAM permissions of the caller"""
        print(f"Testing IAM permissions for project: {project_id}")

        desired_permissions = [
            "compute.disks.create",
            "compute.firewalls.list",
            "compute.firewalls.delete",
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
            "compute.networks.delete",
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

        returnedPermissions: dict = (
            self.service.projects().testIamPermissions(resource=project_id, body=permissions).execute()
        ) or {}

        # check that everything in desired_permissions is in returnedPermissions
        if set(desired_permissions).issubset(set(returnedPermissions.get("permissions", {}))):
            return True

        print(f"Missing permissions: {set(desired_permissions) - set(returnedPermissions.get('permissions', {}))}")
        return False
