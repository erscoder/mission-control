"""CrewAI tools for Sentinel V2 agents."""
from sentinel_v2.tools.file_tool import (
    ListFilesTool,
    RunShellTool,
    WriteFileTool,
)
from sentinel_v2.tools.stripe_tool import (
    StripeCreateProductTool,
    StripeCreateWebhookTool,
    StripeDeleteProductTool,
    StripeListProductsTool,
)
from sentinel_v2.tools.cloudflare_tool import (
    CloudflareDnsCnameTool,
    CloudflarePagesAddCustomDomainTool,
    CloudflarePagesCreateTool,
    CloudflarePagesDeployTool,
    CloudflarePagesSetEnvTool,
)
from sentinel_v2.tools.fly_tool import (
    FlyAppCreateTool,
    FlyDeployTool,
    FlySecretsSetTool,
    FlyStatusTool,
)
from sentinel_v2.tools.osv_scanner_tool import OsvScannerTool

__all__ = [
    # file
    "WriteFileTool",
    "ListFilesTool",
    "RunShellTool",
    # stripe
    "StripeCreateProductTool",
    "StripeListProductsTool",
    "StripeCreateWebhookTool",
    "StripeDeleteProductTool",
    # cloudflare
    "CloudflarePagesCreateTool",
    "CloudflarePagesDeployTool",
    "CloudflarePagesSetEnvTool",
    "CloudflareDnsCnameTool",
    "CloudflarePagesAddCustomDomainTool",
    # fly
    "FlyAppCreateTool",
    "FlySecretsSetTool",
    "FlyDeployTool",
    "FlyStatusTool",
    # osv
    "OsvScannerTool",
]
