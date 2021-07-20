#!/usr/bin/env python3
import os

from aws_cdk import core as cdk

# For consistency with TypeScript code, `cdk` is the preferred import name for
# the CDK's core module.  The following line also imports it as `core` for use
# with examples from the CDK Developer's Guide, which are in the process of
# being updated to use `cdk`.  You may delete this import if you don't need it.
from aws_cdk import (
    core,
    aws_lambda as lambda_,
    aws_apigateway as apigateway
)


class TSOutlierDetectionAPIStack(cdk.Stack):

    def __init__(self, scope: cdk.Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        lambda_func = lambda_.DockerImageFunction(
            scope=self, id="tso-lambda-function",
            code=lambda_.DockerImageCode.from_image_asset(directory="../docker"),
            memory_size=3000,
            timeout=core.Duration.seconds(60)
        )

        api = apigateway.LambdaRestApi(
            self, "tso-apigateway", handler=lambda_func
        )


app = core.App()
TSOutlierDetectionAPIStack(app, "TSOutlierDetectionAPIStack")

app.synth()
