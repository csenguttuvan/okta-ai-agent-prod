resource "aws_lb" "mcp" {
  name               = "okta-mcp-alb"
  internal           = true
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = [aws_subnet.app_private_a.id, aws_subnet.nat_public_a.id]

  enable_deletion_protection = false

  tags = {
    Name = "okta-mcp-alb"
  }
}

resource "aws_lb_target_group" "mcp" {
  name     = "okta-mcp-tg"
  port     = 8080
  protocol = "HTTP"
  vpc_id   = aws_vpc.main.id

  health_check {
    enabled             = true
    healthy_threshold   = 2
    interval            = 30
    matcher             = "200"
    path                = "/health"
    port                = "80"
    protocol            = "HTTP"
    timeout             = 5
    unhealthy_threshold = 2
  }

  tags = {
    Name = "okta-mcp-tg"
  }
}

resource "aws_lb_listener" "mcp" {
  load_balancer_arn = aws_lb.mcp.arn
  port              = "8080"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.mcp.arn
  }
}

# Attach single instance to target group
resource "aws_lb_target_group_attachment" "mcp" {
  target_group_arn = aws_lb_target_group.mcp.arn
  target_id        = aws_instance.mcp_server.id
  port             = 8080
}
