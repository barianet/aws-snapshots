# AWS EBS Snapshots
This simple utility allows you to automatically snapshot EBS volumes across your AWS account(s).

The script is designed to be executed directly from the CLI or some automated process that provides the flags.

## Version
1.0

## Process
The process of the script is as follows:

1. Look for volumes with a tag and tag value (`--tag`, `--tag-value`)
1. Loop over each volume and check the value of the retention (`--tag-retention`) and frequency (`--tag-frequency`) tags
1. Determine if the volume requires a snapshot to be taken based on the frequency, last snapshot taken, and current date/time
1. Determine if the volume has any old snapshots that fall outside of the retention policy and delete them

### Tag & Tag Value
This is the tag used for finding the volumes to begin with. It looks for `--tag` (default: `snapshotbackup`) and a value of `--tag-value` (default: `true`).

### Frequency
The frequency tag is in minutes. It's how often you want to take a snapshot of the volume in minutes.

The tag name defaults to `snapshotbackup_frequency`, but no default frequency policy is assumed.

### Retention
The retention tag is in days. It's how many days you want to retain snapshots for before they're deleted.

The tag name defaults to `snapshotbackup_retention`, but no default retention policy is assumed.

## Command Line Usage
See `-h` for usage details.

## AWS Authentication
To authenticate to AWS, you have several options:

1. CLI flags
1. AWS credentials/config file
1. Point (2) + Profiles
1. Point (3) + Security Token Service

### Command Line Flags
You can use three arguments on the CLI to authenticate against AWS:

1. `--region`
1. `--access-key`
1. `--access-key-secret`

These should be self explanatory to anyone who is familiar with AWS.

### AWS Credentials File
If you use the [AWS credentials or configuration files](http://docs.aws.amazon.com/cli/latest/userguide/cli-chap-getting-started.html#cli-config-files) then you can simply leave the work to the boto library and it'll authenticate automatically for you.

#### Profiles
If you use profiles within your `credentials` or `config` files, however, then you can use the `--profile` flag to tell boto which profile to use.

### AWS STS
If you need to assume an IAM role via STS, boto helps take care of this for you.

All you have to do is create/update your `~./aws/config` file to include a few additional flags under the relevant profile name. The profile name **also needs to take on a particular format.** [See the Boto3 documentation for more details on formatting.](http://boto3.readthedocs.io/en/latest/guide/configuration.html#aws-config-file)

To add a new profile which can assume a role, [see the Boto3 documentation on the Assume Role Provider.](http://boto3.readthedocs.io/en/latest/guide/configuration.html#assume-role-provider) In short, with a few file changes it should be abstracted for you by boto.

## Lambda Support
Lambda support was removed until it can be integrated in a nicer manner (versus just calling `main()`, which doesn't work anymore.)

## Author
Michael Crilly.

## License
MIT