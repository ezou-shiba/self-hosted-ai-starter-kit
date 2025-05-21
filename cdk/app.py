#!/usr/bin/env python3
# -*- encoding: utf-8 -*-

import os
import aws_cdk as cdk
from stacks.vpc_stack import VpcStack
from stacks.rds_stack import RdsStack
from stacks.ecs_stack import EcsStack

app = cdk.App()

# Create VPC Stack
vpc_stack = VpcStack(app, "VpcStack",
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region=os.getenv('CDK_DEFAULT_REGION')
    )
)

# Create RDS Stack
rds_stack = RdsStack(app, "RdsStack",
    vpc=vpc_stack.vpc,
    vpc_stack=vpc_stack,
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region=os.getenv('CDK_DEFAULT_REGION')
    )
)

# Create ECS Stack
ecs_stack = EcsStack(app, "EcsStack",
    vpc=vpc_stack.vpc,
    db_instance=rds_stack.db_instance,
    alb_security_group=vpc_stack.alb_security_group,
    ecs_security_group=vpc_stack.ecs_security_group,
    env=cdk.Environment(
        account=os.getenv('CDK_DEFAULT_ACCOUNT'),
        region=os.getenv('CDK_DEFAULT_REGION')
    )
)

app.synth() 