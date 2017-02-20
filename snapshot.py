
import arrow  # http://crsmithdev.com/arrow/
import boto3  # http://boto3.readthedocs.io/en/latest/reference/services/
import json
import argparse

from random import randint
from multiprocessing.dummy import Pool as ThreadPool 
from datetime import datetime

ec2 = None
ec2_resource = None
cliargs = None

def create_snapshot(volume_name, volume_id):
	"""
	Creates a snapshot of the volume id we pass in.
	This will also tag the snapshot with the volume's Name tag
	contents.
	"""
	if cliargs.verbose:
		print "Will snapshot '%s' and tag it with '%s'" % (volume_id, volume_name)

	response = ec2.create_snapshot(VolumeId=volume_id, Description=volume_name)
	if response:
		ec2.create_tags(Resources=[response["SnapshotId"]], Tags=[{"Key": "Name", "Value": volume_name}])

def process_volume(args):
	'''
	Processes a single volume. This is designed to be used in a multi-threaded manner.

	args = return value from ec2.describe_volumes() 
	See: http://boto3.readthedocs.io/en/latest/reference/services/ec2.html#EC2.Client.describe_volumes
	'''
	volume_name = ""
	for tag in args["Tags"]:
		if tag["Key"] == "Name": volume_name = tag["Value"]

	backup_frequency = None
	backup_retention = None

	# We check for the frequency and retention tags here
	# because we want to detect problems here before making
	# more calls to AWS and wasting time.
	#
	# If the tags don't exist, then we can't work with the
	# volume.
	for tag in args["Tags"]:
		if tag["Key"] == "snapshotbackup_frequency":
			backup_frequency = int(tag["Value"])  # minutes
			if cliargs.verbose:
				print("Backup frequency: %s" % backup_frequency)

		if tag["Key"] == "snapshotbackup_retention":
			backup_retention = int(tag["Value"])  # days
			if cliargs.verbose:
				print("Backup retention: %s" % backup_retention)

	if not backup_retention or not backup_frequency:
		if cliargs.verbose:
			print "Volume '%s' has a 'snapshotbackup' tag, but no frequency or retention tags. Taking no action." % args["VolumeId"]
		return

	# Get a list of all the snapshots for this volume
	# We use a tag key filter on the volume-id as they're the only snapshots we're intested in
	response = ec2.describe_snapshots(Filters=[{"Name": "volume-id", "Values": [args["VolumeId"]]}])
	if response:
		oldest_snapshot = None
		latest_snapshot = None
		script_inception = arrow.get(2017, 1, 1)

		# Loop over the snapshots and work out which is the oldest/latest
		for snapshot in response["Snapshots"]:
			# If neither are defined yet, then the first snapshot
			# is both the latest and oldest (for now)
			if not oldest_snapshot and not latest_snapshot:
				if cliargs.verbose:
					print("Oldest and latest snapshot set to %s" % snapshot["SnapshotId"])
				oldest_snapshot = snapshot
				latest_snapshot = snapshot
				continue 

			# After we loop around, does the snapshot we're looking at
			# now exist in past relative to the last one we marked as
			# oldest? If so, it's the new oldest snapshot
			if snapshot["StartTime"] < oldest_snapshot["StartTime"]:
				if cliargs.verbose:
					print("Older snapshot found: %s" % snapshot["SnapshotId"])
				oldest_snapshot = snapshot
				continue

			# As above, but this time looking for the latest snapshot
			if snapshot["StartTime"] > latest_snapshot["StartTime"]:
				if cliargs.verbose:
					print("Latest snapshot found: %s" % snapshot["SnapshotId"])
				latest_snapshot = snapshot
				continue

		# If this volume has no snapshots at all, then there
		# won't be an oldest or latest, so we just create a snapshot
		# and move on
		if not oldest_snapshot and not latest_snapshot:
			create_snapshot(volume_name, args["VolumeId"])
			return

		# If we do have an oldest or latest snapshot then we
		# can begin working out what to do based on dates.

		# I use the arrow library as it makes dealing with dates easier.
		# We essentially take the latest snapshot's datetime and advance it
		# forward by backup_frequency minutes. That way, if the current UTC
		# time is in the PAST relative to the advanced time, then we know
		# we're NOT due to take a snapshot. Once $now moves into the future
		# beyond the latest snapshot's time, the latest snapshot is now
		# too old and a new one is needed.
		now = arrow.utcnow()
		latest_snapshot_future = arrow.get(latest_snapshot["StartTime"])
		latest_snapshot_future = latest_snapshot_future.replace(minutes=+backup_frequency)

		if cliargs.verbose:
			print("Latest snapshot future UTC (Current UTC: %s): %s" % (arrow.get(latest_snapshot["StartTime"]), latest_snapshot_future))

		if latest_snapshot_future < now:
			create_snapshot(volume_name, args["VolumeId"])

		# Same as above with the latest snapshot, except now we're
		# working out if the oldest snapshot is too old and should
		# be deleted.
		oldest_snapshot_future = arrow.get(oldest_snapshot["StartTime"])
		oldest_snapshot_future = oldest_snapshot_future.replace(days=+backup_retention)

		if cliargs.verbose:
			print("Oldest snapshot future UTC (Current UTC: %s): %s" % (arrow.get(oldest_snapshot["StartTime"]), oldest_snapshot_future))

		if oldest_snapshot_future < now:
			# We ignore any snapshots prior to the inception of
			# this script's creation: 2016-11
			if oldest_snapshot["StartTime"] < script_inception:
				if cliargs.verbose:
					print "Snapshot before inception date. Ignoring."
				return

			if cliargs.verbose:
				print "Will delete old snapshot id %s (%s)" % (oldest_snapshot["SnapshotId"], oldest_snapshot["StartTime"])

			response = ec2.delete_snapshot(SnapshotId=oldest_snapshot["SnapshotId"])

def main():
	global ec2, ec2_resource, cliargs
	parser = argparse.ArgumentParser(fromfile_prefix_chars="@")

	# Tags related flags
	parser.add_argument(
		"--tag",
		help="The tag to filter on and use to find targets for snapshots",
		default="snapshotbackup"
	)

	parser.add_argument(
		"--tag-value",
		help="The tag value to filter on and determine if the volume should be backed up",
		default="true"
	)
	
	parser.add_argument(
		"--tag-frequency",
		help="The tag for determining snapshot frequency",
		default="snapshotbackup_frequency"
	)
	
	parser.add_argument(
		"--tag-retention",
		help="The tag for determining snapshot retention",
		default="snapshotbackup_retention"
	)

	# AWS related flags
	parser.add_argument("--profile",
		help="AWS Profile to use in ~/.aws/credentials",
		default="default"
	)
	
	parser.add_argument("--region",
		help="AWS region to work with",
		default="ap-southeast-2"
	)

	parser.add_argument("--access-key",
		help="AWS API access key ID",
		default=""
	)

	parser.add_argument("--access-key-secret",
		help="AWS API secret key ID",
		default=""
	)

	# Snapshot.py related flags
	parser.add_argument("--verbose",
		"-v",
		help="Verbose output for debugging purposes",
		action="store_true",
		default=False
	)

	cliargs = parser.parse_args()
	boto_args = {
		"region_name": cliargs.region,
		"profile_name": cliargs.profile,
		"aws_access_key_id": cliargs.access_key,
		"aws_secret_access_key": cliargs.access_key_secret,
	}

	aws_session = boto3.session.Session(**boto_args)
	ec2 = aws_session.client("ec2")
	ec2_resource = aws_session.resource("ec2")

	# We fetch a list of volumes in EC2. All of them, but we filter them based
	# on having a tag with the key of `--tag`'s value. This saves us having to
	# do that processing ourselves.
	response = ec2.describe_volumes(Filters=[{
		"Name": "tag:%s" % cliargs.tag,
		"Values": [cliargs.tag_value]
	}])

	if len(response["Volumes"]) > 0:
		# We create a pool of 4 threads and then we loop over the list,
		# mapping each item in the list against the process_volume() function.
		# This is a standard map() as per functional programming.
		pool = ThreadPool(4)
		pool.map(process_volume, response["Volumes"])
	else:
		if cliargs.verbose:
			print "No volumes found."

if __name__ == "__main__":
	main()
