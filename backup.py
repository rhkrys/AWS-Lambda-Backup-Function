import boto3
import json
import collections
import datetime

ec = boto3.client('ec2')

def search(dicts, searchfor):
    for item in dicts:
        if searchfor == item['Key']:
            return item['Value']
    return None
    
def find_name(instance):
    name = filter(lambda tag: tag['Key'] == 'Name', instance['Tags'])[0]['Value']
    return name
 
def lambda_handler(event, context):

    reservations = ec.describe_instances(
        Filters=[
            {'Name': 'tag-key', 'Values': ['backup', 'Backup']},
        ]
    ).get(
        'Reservations', []
    )

    instances = sum(
        [
            [i for i in r['Instances']]
            for r in reservations
        ], [])

    print "Found %d instances that need backing up" % len(instances)

    to_tag = collections.defaultdict(list)
    
    
    for instance in instances:
        try:
            retention_days = [
                int(t.get('Value')) for t in instance['Tags']
                if t['Key'] == 'Retention'][0]
        except IndexError:
            retention_days = 30

        for dev in instance['BlockDeviceMappings']:
            if dev.get('Ebs', None) is None:
                continue
            vol_id = dev['Ebs']['VolumeId']
            descriptioninfo = "DAILY Backup of Instance Name" + find_name(instance)


            print "========================================"
            print "Found EBS volume %s on instance %s" % (
                vol_id, instance['InstanceId'], )
            
            snap = ec.create_snapshot(
                VolumeId=vol_id, Description=descriptioninfo,
            )

            to_tag[retention_days].append(snap['SnapshotId'])

            print "Retaining snapshot %s of volume %s from instance %s for %d days" % (
                snap['SnapshotId'],
                vol_id,
                instance['InstanceId'],
                retention_days,
                )


    for retention_days in to_tag.keys():
        delete_date = datetime.date.today() + datetime.timedelta(days=retention_days)
        delete_fmt = delete_date.strftime('%Y-%m-%d')
        print "Will delete %d snapshots on %s" % (len(to_tag[retention_days]), delete_fmt)
        ec.create_tags(
            Resources=to_tag[retention_days],
            Tags=[
                {'Key': 'DeleteOn', 'Value': delete_fmt},
            ]
        )
