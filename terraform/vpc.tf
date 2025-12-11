# Reference existing corp-it-eu-vpc
data "aws_vpc" "corp_it_eu" {
  filter {
    name   = "tag:Name"
    values = ["corp-it-eu-vpc"]
  }
}

# Reference specific subnet by ID
data "aws_subnet" "private_target" {
  id = "subnet-017db9446e376909c"
}
