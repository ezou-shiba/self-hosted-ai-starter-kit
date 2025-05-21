from aws_cdk import (
    Stack,
    aws_rds as rds,
    aws_ec2 as ec2,
    aws_secretsmanager as secretsmanager,
    Duration,
    RemovalPolicy,
)
from constructs import Construct

class RdsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc, vpc_stack, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create database credentials secret
        self.secret = secretsmanager.Secret(
            self, "AiStarterKitDbSecret",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"username": "dbadmin"}',
                generate_string_key="password",
                exclude_characters="\"@/\\"
            )
        )

        # Create a security parameter group that allows connections from anywhere in the VPC
        pg_params = rds.ParameterGroup(
            self, "DbParams",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15
            ),
            parameters={
                # Allow connections from all IPs in the VPC
                "rds.force_ssl": "0"
            }
        )

        # Create RDS instance
        self.db_instance = rds.DatabaseInstance(
            self, "AiStarterKitDb",
            engine=rds.DatabaseInstanceEngine.postgres(
                version=rds.PostgresEngineVersion.VER_15
            ),
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(
                subnet_type=ec2.SubnetType.PRIVATE_ISOLATED
            ),
            instance_type=ec2.InstanceType.of(
                ec2.InstanceClass.T3,
                ec2.InstanceSize.MICRO
            ),
            allocated_storage=20,
            max_allocated_storage=100,
            database_name="n8n",
            credentials=rds.Credentials.from_secret(self.secret),
            security_groups=[vpc_stack.rds_security_group],
            parameter_group=pg_params,
            backup_retention=Duration.days(7),
            preferred_backup_window="03:00-04:00",
            preferred_maintenance_window="Mon:04:00-Mon:05:00",
            enable_performance_insights=True,
            performance_insight_retention=rds.PerformanceInsightRetention.DEFAULT,
            removal_policy=RemovalPolicy.DESTROY,  # For easy cleanup during development
            deletion_protection=False,            # For easy cleanup during development
            port=5432
        ) 