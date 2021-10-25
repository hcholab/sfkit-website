from src import constants
import googleapiclient.discovery


class GoogleCloudIAM:
    def __init__(self) -> None:
        self.service = googleapiclient.discovery.build("cloudresourcemanager", "v1")
        self.project = constants.SERVER_GCP_PROJECT

    def get_policy(self, version=1):
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

        if role in [b["role"] for b in policy["bindings"]]:
            binding = next(b for b in policy["bindings"] if b["role"] == role)
            binding["members"].append(member)
        else:
            binding = {"role": role, "members": [member]}
            policy["bindings"].append(binding)
        return policy

    def set_policy(self, policy):
        """Sets IAM policy for a project."""

        policy = (
            self.service.projects()
            .setIamPolicy(resource=self.project, body={"policy": policy})
            .execute()
        )
        return policy

    def give_cloud_build_view_permissions(self, user):
        """Gives Cloud Build Viewer permissions to a user."""
        print("Giving Cloud Build Viewer permissions to user: {}".format(user))

        policy = self.get_policy()
        policy = self.modify_policy_add_member(
            policy, "roles/cloudbuild.builds.viewer", f"user:{user}"
        )
        policy = self.modify_policy_add_member(
            policy, "roles/logging.viewer", f"user:{user}"
        )
        self.set_policy(policy)
