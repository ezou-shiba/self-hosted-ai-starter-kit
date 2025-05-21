from aws_cdk import (
    Stack,
    aws_ec2 as ec2,
    CfnOutput,
)
from constructs import Construct

class VpcStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create VPC using IPAM
        self.vpc = ec2.Vpc(
            self, "AiStarterKitVPC",
            ip_addresses=ec2.IpAddresses.aws_ipam_allocation(
                ipv4_ipam_pool_id="ipam-pool-03b27f5d788beda16",
                ipv4_netmask_length=16
            ),
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="Public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=20
                ),
                ec2.SubnetConfiguration(
                    name="Private",
                    subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS,
                    cidr_mask=20
                ),
                ec2.SubnetConfiguration(
                    name="Isolated",
                    subnet_type=ec2.SubnetType.PRIVATE_ISOLATED,
                    cidr_mask=20
                )
            ],
            gateway_endpoints={
                "S3": ec2.GatewayVpcEndpointOptions(
                    service=ec2.GatewayVpcEndpointAwsService.S3
                )
            }
        )

        # Create security group for ALB
        self.alb_security_group = ec2.SecurityGroup(
            self, "AiStarterKitAlbSg",
            vpc=self.vpc,
            description="Security group for AI Starter Kit ALB",
            allow_all_outbound=True
        )

        # Allow inbound HTTP from specific IP to ALB
        self.alb_security_group.add_ingress_rule(
            ec2.Peer.ipv4("73.241.100.231/32"),
            ec2.Port.tcp(80),
            "Allow HTTP from specific IP"
        )
        
        # Allow inbound Qdrant access from specific IP to ALB
        self.alb_security_group.add_ingress_rule(
            ec2.Peer.ipv4("73.241.100.231/32"),
            ec2.Port.tcp(6333),
            "Allow Qdrant access from specific IP"
        )

        # Create security group for ECS tasks
        self.ecs_security_group = ec2.SecurityGroup(
            self, "AiStarterKitEcsSg",
            vpc=self.vpc,
            description="Security group for AI Starter Kit ECS tasks",
            allow_all_outbound=True
        )

        # Allow inbound access from ALB
        self.ecs_security_group.add_ingress_rule(
            self.alb_security_group,
            ec2.Port.tcp(5678),
            "Allow n8n access from ALB"
        )

        # Allow container-to-container communication
        self.ecs_security_group.add_ingress_rule(
            self.ecs_security_group,
            ec2.Port.tcp(11434),
            "Allow Ollama access from containers"
        )
        self.ecs_security_group.add_ingress_rule(
            self.ecs_security_group,
            ec2.Port.tcp(6333),
            "Allow Qdrant access from containers"
        )

        # Create security group for RDS
        self.rds_security_group = ec2.SecurityGroup(
            self, "AiStarterKitRdsSg",
            vpc=self.vpc,
            description="Security group for AI Starter Kit RDS",
            allow_all_outbound=True
        )

        # Allow PostgreSQL access from ECS
        self.rds_security_group.add_ingress_rule(
            self.ecs_security_group,
            ec2.Port.tcp(5432),
            "Allow PostgreSQL access from ECS"
        )
        
        # Also allow PostgreSQL access from any IP in the VPC
        self.rds_security_group.add_ingress_rule(
            ec2.Peer.ipv4(self.vpc.vpc_cidr_block),
            ec2.Port.tcp(5432),
            "Allow PostgreSQL access from anywhere in VPC"
        )

        # Export VPC ID
        CfnOutput(self, 'AiStarterKitVpcId', 
            value=self.vpc.vpc_id,
            export_name=f'{self.stack_name}-VpcId'
        ) 