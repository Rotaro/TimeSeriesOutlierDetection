# Bash commands for setting up API in aws 

# Choose a stack name
export STACK_NAME=tso-test

# Create s3 bucket for nested templates and codebuild artifacts
aws cloudformation create-stack --stack-name $STACK_NAME-s3 --template-body file://cloudformation/1-s3-bucket.yaml --parameters ParameterKey=DeploymentName,ParameterValue=tso-test --capabilities CAPABILITY_NAMED_IAM
# Wait until stack is ready..
aws cloudformation stack-create-complete --stack_name $STACK_NAME-s3

# Find s3 bucket name to upload templates / codebuild artifacts
export BUCKET_NAME=`aws cloudformation describe-stacks --stack-name $STACK_NAME-s3 --query "Stacks[].Outputs[?OutputKey=='Bucket'].OutputValue" --output text`

# Update nested stack templates and upload them to s3 (update = change location of nested templates to s3)
aws cloudformation package --template-file cloudformation/2-iam-ecr-codebuild-parent.yaml --s3-bucket $BUCKET_NAME --output-template-file 2-iam-ecr-codebuild-parent-updated.yaml 


# Zip and copy files to s3 for building docker image using CodeBuild
"/c/Program Files/7-Zip/7z" a -tzip -- codebuild.zip ./docker/*
aws s3 cp codebuild.zip s3://$BUCKET_NAME/codebuild.zip

# Create ECR & CodeBuild project 
aws cloudformation create-stack --stack-name $STACK_NAME-build --template-body file://2-iam-ecr-codebuild-parent-updated.yaml --parameters ParameterKey=DeploymentName,ParameterValue=tso-test --capabilities CAPABILITY_NAMED_IAM
# Wait until stack is ready..
aws cloudformation stack-create-complete --stack_name $STACK_NAME-build

# Find Codebuild project and run it (=build docker image)
export CODEBUILD_PROJECT=`aws cloudformation list-exports --query "Exports[?(contains(Name, '$STACK_NAME') && contains(Name, 'CodeBuildProject'))].Value" --output text`
aws codebuild start-build --project-name $CODEBUILD_PROJECT

# This will output the build id:
#{
    #"build": {
        #"id": "DockerBuild-fdLRyGK1E26p:4e4a1e49-954e-46ab-970c-a6c9ddc2e7ca",
# Manually check until build is finished.. (less than 10 minutes)
aws codebuild batch-get-builds --ids DockerBuild-fdLRyGK1E26p:4e4a1e49-954e-46ab-970c-a6c9ddc2e7ca --query "builds[0].buildComplete"

# Finally create lambda function and deploy API gateway
aws cloudformation create-stack --stack-name $STACK_NAME-api --template-body file://cloudformation/3-lambda-apigateway.yaml --parameters ParameterKey=DeploymentName,ParameterValue=tso-test --capabilities CAPABILITY_NAMED_IAM
# Wait until stack is ready..
aws cloudformation stack-create-complete --stack_name $STACK_NAME-api

# Get API URL
export API_URL=`aws cloudformation describe-stacks --stack-name $STACK_NAME-api --query "Stacks[].Outputs[?OutputKey=='ApiGatewayInvokeURL'].OutputValue" --output text`

# Test api using curl (note: first call can be slow / timeout as docker image isn't cached in any way)
curl -H "Content-Type: application/json" -X POST -d @test_data.json $API_URL


# Clean up 
aws cloudformation delete-stack --stack-name $STACK_NAME-api

# Need to force delete ECR since it contains image
export ECR_NAME=`aws cloudformation list-exports --query "Exports[?(contains(Name, '$STACK_NAME') && contains(Name, 'ECRName'))].Value" --output text`
aws ecr delete-repository --repository-name $ECR_NAME --force

aws cloudformation delete-stack --stack-name $STACK_NAME-build

# Need to force delete s3 bucket since it contains files
aws s3 rb s3://$BUCKET_NAME --force
aws cloudformation delete-stack --stack-name $STACK_NAME-s3
