resource "aws_vpc" "mcp" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "mcp-vpc"
  }
}

resource "aws_internet_gateway" "mcp" {
  vpc_id = aws_vpc.mcp.id

  tags = {
    Name = "mcp-igw"
  }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.mcp.id
  cidr_block              = "10.0.1.0/24"
  map_public_ip_on_launch = true
  availability_zone       = "${var.aws_region}a"

  tags = {
    Name = "mcp-public-subnet"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.mcp.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.mcp.id
  }

  tags = {
    Name = "mcp-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}
