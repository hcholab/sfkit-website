
import os
import subprocess
from re import I


class GoogleCloudGeneral:

    def __init__(self, project) -> None:
        self.project = project

    # Execute series of shell commands on Google Cloud Compute Instance
    def execute_shell_script_on_instance(self, instance, cmds):
        cmd = '; '.join(cmds)
        script = 'gcloud compute ssh {} --project {} --command \'{}\''.format(
            instance, self.project, cmd)
        return subprocess.Popen(script, shell=True).wait()
