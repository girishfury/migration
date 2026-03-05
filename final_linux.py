import boto3
import time
import json

# -------------------------------
# AWS Clients
# -------------------------------
ec2 = boto3.client("ec2", region_name="us-east-1")
ssm = boto3.client("ssm", region_name="us-east-1")


def lambda_handler(event, context):

    print("\n========== EXECUTION START ==========\n")

    instances_data = event.get("instances", [])
    if not instances_data:
        print("❌ No instances provided")
        return {"error": "instances list not provided in event"}

    results = []

    for inst_data in instances_data:

        instance_id = inst_data.get("instance_id")
        migration_id = inst_data.get("migration_id", "N/A")

        print(f"[START] Instance: {instance_id} | Migration: {migration_id}\n")

        if not instance_id:
            print("❌ Instance ID missing\n")
            continue

        try:
            # --------------------------------------------------
            # STEP 1 – EC2 DETAILS
            # --------------------------------------------------
            print("STEP 1: Fetching EC2 details")

            response = ec2.describe_instances(InstanceIds=[instance_id])
            instance = response["Reservations"][0]["Instances"][0]

            state = instance.get("State", {}).get("Name")
            private_ip = instance.get("PrivateIpAddress")
            public_ip = instance.get("PublicIpAddress")
            platform_details = instance.get("PlatformDetails")

            print(f"  State      : {state}")
            print(f"  Private IP : {private_ip}")
            print(f"  Public IP  : {public_ip}")
            print(f"  Platform   : {platform_details}\n")

            if state != "running":
                print("❌ Instance not running\n")
                continue

            # --------------------------------------------------
            # STEP 2 – 3/3 STATUS
            # --------------------------------------------------
            print("STEP 2: Checking 3/3 Status")

            status_response = ec2.describe_instance_status(
                InstanceIds=[instance_id],
                IncludeAllInstances=True
            )

            system_status = None
            instance_status = None
            ebs_status = None

            if status_response.get("InstanceStatuses"):
                st = status_response["InstanceStatuses"][0]
                system_status = st.get("SystemStatus", {}).get("Status")
                instance_status = st.get("InstanceStatus", {}).get("Status")
                ebs_status = st.get("AttachedEbsStatus", {}).get("Status")

            checks_3of3_passed = (
                system_status == "ok" and
                instance_status == "ok" and
                ebs_status == "ok"
            )

            print(f"  System    : {system_status}")
            print(f"  Instance  : {instance_status}")
            print(f"  EBS       : {ebs_status}")
            print(f"  3/3 Pass  : {checks_3of3_passed}\n")

            # --------------------------------------------------
            # STEP 3 – SSM PING
            # --------------------------------------------------
            print("STEP 3: Checking SSM Ping")

            ssm_info = ssm.describe_instance_information(
                Filters=[{'Key': 'InstanceIds', 'Values': [instance_id]}]
            )

            ssm_ping_status = None
            if ssm_info.get("InstanceInformationList"):
                ssm_ping_status = ssm_info["InstanceInformationList"][0].get("PingStatus")

            print(f"  SSM Ping  : {ssm_ping_status}\n")

            # --------------------------------------------------
            # STEP 4 – RUN SSM COMMANDS
            # --------------------------------------------------
            print("STEP 4: Running SSH + Port + Hosts Checks\n")

            command_response = ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName="AWS-RunShellScript",
                Parameters={
                    "commands": [

                        # SSH STATUS
                        'echo ""',
                        'echo "==============================="',
                        'echo "===== SSH Service Status ====="',
                        'echo "==============================="',
                        "systemctl is-active sshd",
                        'echo ""',

                        # PORT 22 STATUS
                        'echo "==============================="',
                        'echo "===== Port 22 Listening ====="',
                        'echo "==============================="',
                        "ss -tlnp | grep :22 || echo 'Port 22 not listening'",
                        'echo ""',

                        # HOSTS BEFORE
                        'echo "==============================="',
                        'echo "===== /etc/hosts BEFORE UPDATE ====="',
                        'echo "==============================="',
                        "cat /etc/hosts",
                        'echo ""',

                        # UPDATE HOSTS
                        'echo "==============================="',
                        'echo "===== Updating /etc/hosts ====="',
                        'echo "==============================="',
                        'grep -q "added via automation" /etc/hosts || echo "#added via automation 10.10.10.10 myapp.local" >> /etc/hosts',
                        'echo ""',

                        # HOSTS AFTER
                        'echo "==============================="',
                        'echo "===== /etc/hosts AFTER UPDATE ====="',
                        'echo "==============================="',
                        "cat /etc/hosts",
                        'echo ""',

                        # VERIFY
                        'echo "==============================="',
                        'echo "===== Verify Automation Entry ====="',
                        'echo "==============================="',
                        'grep "added via automation" /etc/hosts || echo "No automation entry found"',
                        'echo ""'
                    ]
                },
                TimeoutSeconds=60
            )

            command_id = command_response["Command"]["CommandId"]
            print(f"  SSM Command ID : {command_id}\n")

            ssm_output = ""

            for _ in range(8):
                time.sleep(5)
                invocation = ssm.get_command_invocation(
                    CommandId=command_id,
                    InstanceId=instance_id
                )

                if invocation["Status"] in ["Success", "Failed", "TimedOut"]:
                    ssm_output = invocation.get("StandardOutputContent", "")
                    break

            print("SSM RAW OUTPUT:\n")
            print(ssm_output)
            print("")

            # --------------------------------------------------
            # PARSE RESULTS
            # --------------------------------------------------
            ssh_service_status = "inactive"
            ssh_port_status = "closed"
            host_entry_status = "failed"

            lines = ssm_output.splitlines()

            for line in lines:
                if line.strip() == "active":
                    ssh_service_status = "active"

                if "LISTEN" in line and ":22" in line:
                    ssh_port_status = "open"

                if "added via automation" in line:
                    host_entry_status = "passed"

            # --------------------------------------------------
            # FINAL RESULT JSON
            # --------------------------------------------------
            results.append({
                "instance_id": instance_id,
                "migration_id": migration_id,
                "private_ip": private_ip,
                "public_ip": public_ip,
                "platform_details": platform_details,
                "state": state,
                "system_status": system_status,
                "instance_status": instance_status,
                "ebs_status": ebs_status,
                "checks_3of3_passed": checks_3of3_passed,
                "ssm_ping_status": ssm_ping_status,
                "ssh_service_status": ssh_service_status,
                "ssh_port_status": ssh_port_status,
                "host_entry_status": host_entry_status
            })

            print(f"[END] Completed {instance_id}")
            print("--------------------------------------------------\n")

        except Exception as e:
            print(f"❌ ERROR: {str(e)}\n")

    print("========== EXECUTION END ==========\n")

    return {
        "status": "success",
        "count": len(results),
        "results": results
    }


# -------------------------------
# LOCAL TEST RUN
# -------------------------------
if __name__ == "__main__":

    test_event = {
        "instances": [
            {"instance_id": "i-0a4c403c71250437b", "migration_id": "mig--linux"},
            {"instance_id": "i-01d9138acd931d64a", "migration_id": "mig-123-debian"},
            {"instance_id": "i-0294087641e2cadf2", "migration_id": "mig-123-ubuntu"},
            {"instance_id": "i-022acf12a4d931521", "migration_id": "mig-123-redhat"}

        ]
    }

    output = lambda_handler(test_event, None)

    print("FINAL JSON OUTPUT:\n")
    print(json.dumps(output, indent=2))
