from aws_cdk import (
    Stack,
    aws_ecs as ecs,
    aws_ec2 as ec2,
    aws_elasticloadbalancingv2 as elbv2,
    aws_logs as logs,
    aws_iam as iam,
    RemovalPolicy,
    CfnOutput
)
from aws_cdk import Duration  # Import Duration separately
from constructs import Construct
import uuid

class EcsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, vpc: ec2.Vpc, db_instance, alb_security_group, ecs_security_group, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create ECS Cluster
        self.cluster = ecs.Cluster(
            self, "Cluster",
            vpc=vpc,
            container_insights=True
        )

        # Create Task Execution Role
        execution_role = iam.Role(
            self, "TaskExecutionRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name(
                    "service-role/AmazonECSTaskExecutionRolePolicy"
                )
            ]
        )

        # Create Task Role
        task_role = iam.Role(
            self, "TaskRole",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("AmazonS3ReadOnlyAccess"),
                iam.ManagedPolicy.from_aws_managed_policy_name("CloudWatchLogsFullAccess")
            ]
        )

        # Create Log Group
        log_group = logs.LogGroup(
            self, "LogGroup",
            log_group_name="/ecs/ai-starter-kit",
            retention=logs.RetentionDays.ONE_MONTH
        )

        # Create Task Definition
        task_definition = ecs.FargateTaskDefinition(
            self, "TaskDefinition",
            memory_limit_mib=4096,
            cpu=2048,
            execution_role=execution_role,
            task_role=task_role
        )

        # Add n8n Container
        n8n_container = task_definition.add_container(
            "n8n",
            image=ecs.ContainerImage.from_registry("n8nio/n8n:latest"),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="n8n",
                log_group=log_group
            ),
            environment={
                "DB_TYPE": "postgresdb",
                "DB_POSTGRESDB_HOST": db_instance.db_instance_endpoint_address,
                "DB_POSTGRESDB_USER": "dbadmin",
                "N8N_DIAGNOSTICS_ENABLED": "false",
                "N8N_PERSONALIZATION_ENABLED": "false",
                "OLLAMA_HOST": "localhost:11434",
                "N8N_SECURE_COOKIE": "false"
            },
            secrets={
                "DB_POSTGRESDB_PASSWORD": ecs.Secret.from_secrets_manager(
                    db_instance.secret,
                    field="password"
                )
            }
        )
        n8n_container.add_port_mappings(
            ecs.PortMapping(
                container_port=5678,
                host_port=5678,
                protocol=ecs.Protocol.TCP
            )
        )

        # Add Ollama Container
        ollama_container = task_definition.add_container(
            "ollama",
            image=ecs.ContainerImage.from_registry("ollama/ollama:latest"),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="ollama",
                log_group=log_group
            )
        )
        ollama_container.add_port_mappings(
            ecs.PortMapping(
                container_port=11434,
                host_port=11434,
                protocol=ecs.Protocol.TCP
            )
        )

        # Add Qdrant Container
        qdrant_container = task_definition.add_container(
            "qdrant",
            image=ecs.ContainerImage.from_registry("qdrant/qdrant"),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="qdrant",
                log_group=log_group
            )
        )
        qdrant_container.add_port_mappings(
            ecs.PortMapping(
                container_port=6333,
                host_port=6333,
                protocol=ecs.Protocol.TCP
            )
        )

        # Create Application Load Balancer
        alb = elbv2.ApplicationLoadBalancer(
            self, "ALB",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_security_group
        )

        # Create Target Group for n8n
        n8n_target_group = elbv2.ApplicationTargetGroup(
            self, "TargetGroup",
            vpc=vpc,
            port=5678,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                path="/",
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=2
            )
        )

        # Create Target Group for Qdrant
        qdrant_target_group = elbv2.ApplicationTargetGroup(
            self, "QdrantTargetGroup",
            vpc=vpc,
            port=6333,
            protocol=elbv2.ApplicationProtocol.HTTP,
            target_type=elbv2.TargetType.IP,
            health_check=elbv2.HealthCheck(
                path="/",
                interval=Duration.seconds(30),
                timeout=Duration.seconds(5),
                healthy_threshold_count=2,
                unhealthy_threshold_count=2
            )
        )

        # Add n8n Listener
        alb.add_listener(
            "Listener",
            port=80,
            default_target_groups=[n8n_target_group]
        )
        
        # Add Qdrant Listener
        alb.add_listener(
            "QdrantListener",
            port=6333,
            default_target_groups=[qdrant_target_group]
        )

        # Create ECS Service
        service = ecs.FargateService(
            self, "Service",
            cluster=self.cluster,
            task_definition=task_definition,
            desired_count=1,
            security_groups=[ecs_security_group],
            assign_public_ip=True
        )

        # Add service to target groups
        service.attach_to_application_target_group(n8n_target_group)
        service.attach_to_application_target_group(qdrant_target_group)
        
        # Add Stack Outputs
        CfnOutput(
            self, "LoadBalancerDNS",
            value=alb.load_balancer_dns_name,
            description="DNS name of the load balancer for n8n access"
        )
        
        CfnOutput(
            self, "N8nUrl",
            value=f"http://{alb.load_balancer_dns_name}",
            description="URL to access the n8n interface"
        )
        
        CfnOutput(
            self, "OllamaEndpoint",
            value=f"http://{alb.load_balancer_dns_name}:11434",
            description="Endpoint for Ollama API (accessible from n8n only)"
        )
        
        CfnOutput(
            self, "QdrantEndpoint",
            value=f"http://{alb.load_balancer_dns_name}:6333",
            description="Endpoint for Qdrant API (accessible from n8n only)"
        )
        
        CfnOutput(
            self, "QdrantDashboard",
            value=f"http://{alb.load_balancer_dns_name}:6333/dashboard",
            description="URL to access the Qdrant Dashboard"
        ) 