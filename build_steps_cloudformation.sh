#!/bin/bash -e
# #####################
# Setting up Time Series Outlier Detection API in AWS using Cloudformation

# 0. Choose a stack name
export STACK_NAME=tso-test

###############################
# 1. Create s3 bucket for nested templates and codebuild artifacts
aws cloudformation create-stack \
  --stack-name $STACK_NAME-s3 \
  --template-body file://cloudformation/1-s3-bucket.yaml \
  --parameters ParameterKey=DeploymentName,ParameterValue=tso-test \
  --capabilities CAPABILITY_NAMED_IAM

# Wait until stack is ready
aws cloudformation wait stack-create-complete --stack-name $STACK_NAME-s3

# Save bucket name
export BUCKET_NAME=`aws cloudformation describe-stacks \
                      --stack-name $STACK_NAME-s3 \
                      --query "Stacks[].Outputs[?OutputKey=='S3BucketName'].OutputValue" \
                      --output text`

###############################
# 2. Setup ECR & CodeBuild project for building docker image
# 2 a) Update nested templates and upload them to s3
aws cloudformation package \
  --template-file cloudformation/2-iam-ecr-codebuild-parent.yaml \
  --s3-bucket $BUCKET_NAME \
  --output-template-file 2-iam-ecr-codebuild-parent-updated.yaml

# 2 b) Create ECR & CodeBuild project
aws cloudformation create-stack \
  --stack-name $STACK_NAME-build \
  --template-body file://2-iam-ecr-codebuild-parent-updated.yaml \
  --parameters ParameterKey=DeploymentName,ParameterValue=tso-test \
  --capabilities CAPABILITY_NAMED_IAM

# Wait until stack is ready
aws cloudformation wait stack-create-complete --stack-name $STACK_NAME-build

###############################
# 3. Create docker image for labmda function
# 3 a) Zip and copy files to s3 for building docker image using CodeBuild
"/c/Program Files/7-Zip/7z" a -tzip -- codebuild.zip ./docker/*
aws s3 cp codebuild.zip s3://$BUCKET_NAME/codebuild.zip

# 3 b) Run Codebuild project (= build docker image)
export CODEBUILD_PROJECT=`aws cloudformation list-exports \
                            --query "Exports[?(contains(Name, '$STACK_NAME') && contains(Name, 'CodeBuildProject'))].Value" \
                            --output text`
export BUILD_ID=`aws codebuild start-build --project-name $CODEBUILD_PROJECT --query build.id --output text`

# Manually check until build is finished.. (takes less than 10 minutes)
until [[ `aws codebuild batch-get-builds \
            --ids "$BUILD_ID" \
            --query "builds[0].buildComplete" \
            --output text` == "True" ]];
do
  echo "CodeBuild not yet ready, waiting 30 seconds until checking again.."
  sleep 30
done

echo "CodeBuild ready!"

###############################
# 4. Deploy Lambda function and API
aws cloudformation create-stack \
  --stack-name $STACK_NAME-api \
  --template-body file://cloudformation/3-lambda-apigateway.yaml \
  --parameters ParameterKey=DeploymentName,ParameterValue=tso-test \
  --capabilities CAPABILITY_NAMED_IAM

# Wait until stack is ready
aws cloudformation wait stack-create-complete --stack-name $STACK_NAME-api

###############################
# 5. Test API
export API_URL=`aws cloudformation describe-stacks \
                  --stack-name $STACK_NAME-api \
                  --query "Stacks[].Outputs[?OutputKey=='ApiGatewayInvokeURL'].OutputValue" \
                  --output text`

# Test api using curl (note: first call can be slow / timeout as docker image isn't cached)
echo "Test response from API:"
echo `curl -s -H "Content-Type: application/json" -X POST -d @test/test_data.json $API_URL`

###############################
# 6. Clean up
# Need to force delete ECR since it contains image
export ECR_NAME=`aws cloudformation list-exports \
                   --query "Exports[?(contains(Name, '$STACK_NAME') && contains(Name, 'ECRName'))].Value" \
                   --output text`
aws ecr delete-repository --repository-name $ECR_NAME --force

# Need to force delete s3 bucket since it contains files
aws s3 rb s3://$BUCKET_NAME --force

aws cloudformation delete-stack --stack-name $STACK_NAME-api
aws cloudformation delete-stack --stack-name $STACK_NAME-build
aws cloudformation delete-stack --stack-name $STACK_NAME-s3
