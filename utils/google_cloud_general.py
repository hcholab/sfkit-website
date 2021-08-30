
import os
import subprocess
from re import I


class GoogleCloudGeneral:

    def __init__(self, project) -> None:
        self.project = project

    # Copy file from local machine to Google Cloud Compute Instance
    def transfer_file_to_instance(self, instance, fname, path, zone="us-central1-a"):
        cmd = 'gcloud compute scp --project {} "{}" {}:{} --zone {}'.format(
            self.project, fname, instance, path, zone)
        os.system(cmd)

    # Execute series of shell commands on Google Cloud Compute Instance
    def execute_shell_script_on_instance(self, instance, cmds):
        cmd = '; '.join(cmds)
        script = 'gcloud compute ssh {} --project {} --command \'{}\''.format(
            instance, self.project, cmd)
        # os.system(script)
        return subprocess.Popen(script, shell=True).wait()
