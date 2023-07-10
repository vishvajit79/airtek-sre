import pulumi
import pulumi_aws as aws
import pulumi_docker as docker

# Create an AWS resource group
stack_name = pulumi.get_stack()
resource_group = aws.ResourceGroupsGroup(stack_name)

# Create a VPC
vpc = aws.ec2.Vpc("vpc",
    cidr_block="10.0.0.0/16",
    enable_dns_hostnames=True,
    tags={
        "Name": "airtek-vpc",
    })

# Create a public subnet within the VPC
subnet = aws.ec2.Subnet("subnet",
    vpc_id=vpc.id,
    cidr_block="10.0.0.0/24",
    availability_zone="us-west-2a",
    tags={
        "Name": "public-subnet",
    })

# Create a security group for the web UI
web_ui_security_group = aws.ec2.SecurityGroup("web-ui-security-group",
    vpc_id=vpc.id,
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            cidr_blocks=["0.0.0.0/0"],  # Allow access from anywhere
        ),
    ],
    tags={
        "Name": "web-ui-security-group",
    })

# Create a security group for the API
api_security_group = aws.ec2.SecurityGroup("api-security-group",
    vpc_id=vpc.id,
    ingress=[
        aws.ec2.SecurityGroupIngressArgs(
            protocol="-1",
            from_port=0,
            to_port=0,
            source_security_group_id=web_ui_security_group.id,  # Allow access only from the web UI security group
        ),
    ],
    tags={
        "Name": "api-security-group",
    })

# Create an EC2 instance for the web UI
web_ui_instance = aws.ec2.Instance("web-ui-instance",
    instance_type="t2.micro",
    vpc_security_group_ids=[web_ui_security_group.id],
    subnet_id=subnet.id,
    ami="ami-0c94855ba95c71c99",  # Replace with your desired AMI ID for ASP.NET
    tags={
        "Name": "web-ui-instance",
    })

# Create an API Gateway with a private endpoint
api_gateway = aws.apigatewayv2.Api("api-gateway",
    protocol_type="HTTP",
    target="HTTP://127.0.0.1",  # Replace with your API endpoint
    tags={
        "Name": "api-gateway",
    })

# Associate the API Gateway with the API security group
api_security_group_ingress_rule = aws.ec2.SecurityGroupIngress("api-security-group-ingress",
    description="Allow access from API Gateway",
    security_group_id=api_security_group.id,
    source_security_group_id=api_gateway.security_group_id)

# Deploy the ASP.NET web application using Docker
web_ui_image = docker.Image("web-ui-image",
    image_name="my-web-ui-image",
    build="./infra-web",
    skip_push=True)

web_ui_container = aws.ecs.ContainerDefinition("web-ui-container",
    image=web_ui_image.image_name,
    memory=256,
    cpu=256)

web_ui_task = aws.ecs.TaskDefinition("web-ui-task",
    container_definitions=web_ui_container.container_definitions)

web_ui_service = aws.ecs.Service("web-ui-service",
    task_definition=web_ui_task.arn,
    desired_count=1,
    launch_type="FARGATE",
    network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
        assign_public_ip=True,
        security_groups=[web_ui_security_group.id],
        subnets=[subnet.id],
    ))

# Deploy the API using Docker
api_image = docker.Image("api-image",
    image_name="my-api-image",
    build="./infra-api",
    skip_push=True)

api_container = aws.ecs.ContainerDefinition("api-container",
    image=api_image.image_name,
    memory=256,
    cpu=256)

api_task = aws.ecs.TaskDefinition("api-task",
    container_definitions=api_container.container_definitions)

api_service = aws.ecs.Service("api-service",
    task_definition=api_task.arn,
    desired_count=1,
    launch_type="FARGATE",
    network_configuration=aws.ecs.ServiceNetworkConfigurationArgs(
        security_groups=[api_security_group.id],
        subnets=[subnet.id],
    ))

# Output the URL of the web UI
pulumi.export("web_ui_url", web_ui_instance.public_dns)

# Output the API Gateway URL
pulumi.export("api_gateway_url", api_gateway.api_endpoint)
