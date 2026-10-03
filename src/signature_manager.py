import logging

from src.exchange_client import ExchangeClient
from src.graph_client import GraphClient
from src.signatures import personalize, sanitize_html

logger = logging.getLogger(__name__)


class OutlookSignatureManager:
    """Reads users from Microsoft Graph and writes their Outlook signatures
    through Exchange Online."""

    def __init__(self, graph: GraphClient | None = None, exchange: ExchangeClient | None = None):
        self.graph = graph or GraphClient()
        self.exchange = exchange or ExchangeClient()

    def get_all_users(self) -> list[dict]:
        return self.graph.get_all_users()

    def get_user_signature(self, user_principal_name: str) -> str:
        return self.exchange.get_signature(user_principal_name)

    def set_user_signature(self, user_principal_name: str, signature_html: str) -> None:
        """Set a signature as given (sanitised, not personalised)."""
        self.exchange.set_signature(user_principal_name, sanitize_html(signature_html))

    def apply_template_to_user(self, user_principal_name: str, template: str) -> str:
        user = self.graph.get_user(user_principal_name)
        signature = personalize(template, user)
        self.exchange.set_signature(user_principal_name, signature)
        return signature

    def apply_standard_signature_to_all(self, signature_template: str) -> dict:
        """Personalise the template for every user and write it in batches."""
        signatures = {}
        for user in self.graph.get_all_users():
            upn = user.get("userPrincipalName")
            # Users without a mailbox will fail in Exchange; those without
            # a mail address almost never have one, so skip them up front.
            if upn and user.get("mail"):
                signatures[upn] = personalize(signature_template, user)

        results = {"success": [], "failed": []}
        for result in self.exchange.set_signatures(signatures):
            if result.get("ok"):
                results["success"].append(result["upn"])
            else:
                results["failed"].append({"user": result["upn"], "error": result.get("error")})
                logger.warning("Signature failed for %s: %s", result["upn"], result.get("error"))
        logger.info(
            "Bulk signature update: %d succeeded, %d failed",
            len(results["success"]), len(results["failed"]),
        )
        return results

    def set_automatic_reply(self, user_principal_name: str, message: str,
                            start_time: str | None = None, end_time: str | None = None) -> None:
        self.graph.set_automatic_reply(user_principal_name, message, start_time, end_time)
