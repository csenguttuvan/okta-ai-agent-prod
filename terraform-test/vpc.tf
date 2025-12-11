# VPC
resource "aws_vpc" "okta_mcp" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name        = "okta-mcp-vpc"
    Environment = "test"
  }
}

# Internet Gateway
resource "aws_internet_gateway" "okta_mcp" {
  vpc_id = aws_vpc.okta_mcp.id

  tags = {
    Name        = "okta-mcp-igw"
    Environment = "test"
  }
}

# Public Subnet
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.okta_mcp.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name        = "okta-mcp-public-subnet"
    Environment = "test"
  }
}

# Route Table
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.okta_mcp.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.okta_mcp.id
  }

  tags = {
    Name        = "okta-mcp-public-rt"
    Environment = "test"
  }
}

# Route Table Association
resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}
