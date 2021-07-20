# Deployment using AWS CDK

## Prerequisites
You will need to have [AWS CDK](https://aws.amazon.com/cdk/) and [docker](https://www.docker.com/) installed.

## Setting up CDK python environment
### Preparing python environment
Create a new virtual environment (unless you want to use your current one...):
```
$ python -m venv .venv
```
Activate virtual environment:
```
$ source .venv/bin/activate
```
Install needed aws cdk python packages:
```
$ pip install -r requirements.txt
```

### Bootstrap account-region
The CDK deployment will require [modern bootstrapping](https://docs.aws.amazon.com/cdk/latest/guide/bootstrapping.html) 
of AWS account / region:
```
$ CDK_NEW_BOOTSTRAP=1 cdk bootstrap aws:/account-number/region
```

### Deploy API
```
$ cdk deploy
```
The deployment will ask for permissions to create IAM roles etc., answer yes. 
Once the deployment is complete, the API endpoint will be printed:
```
Outputs:
TSOutlierDetectionAPIStack.tsoapigatewayEndpointXYZ = https://XYZ.execute-api.region-here.amazonaws.com/prod/
...
```

### Cleanup
```
cdk destroy
```
