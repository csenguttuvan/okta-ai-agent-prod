output "mcp_private_ip" {
  description = "MCP server private IP (give to security team for strongDM registration)"
  value       = aws_instance.mcp_server.private_ip
}

output "mcp_instance_id" {
  description = "MCP server EC2 instance ID"
  value       = aws_instance.mcp_server.id
}

output "vpc_id" {
  description = "VPC where MCP is deployed"
  value       = data.aws_vpc.corp_it_eu.id
}

output "strongdm_registration_info" {
  value = <<-EOT
    
    ========================================
    Give this info to Security Team:
    ========================================
    
    MCP Server Details:
    - Instance ID: ${aws_instance.mcp_server.id}
    - Private IP: ${aws_instance.mcp_server.private_ip}
    - VPC: ${data.aws_vpc.corp_it_eu.id}
    - Subnet: ${data.aws_subnet.private_target.id}
    - SSH User: ec2-user
    
    Request: Please register this server in strongDM as:
    - Name: okta-mcp-server
    - Type: SSH
    - Port: 22
    - Access: IT-Team group
    
    ========================================
  EOT
}
