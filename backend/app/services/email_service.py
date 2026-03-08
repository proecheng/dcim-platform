"""
邮件服务 - Story 26.2
支持优雅降级：邮件服务不可用时静默失败
"""

import logging
from typing import List, Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

logger = logging.getLogger(__name__)


class EmailService:
    """邮件服务 - 优雅降级：SMTP 不可用时静默失败"""

    def __init__(self) -> None:
        self._enabled = False
        self._smtp_host: Optional[str] = None
        self._smtp_port: Optional[int] = None
        self._smtp_user: Optional[str] = None
        self._smtp_password: Optional[str] = None
        self._from_email: Optional[str] = None

    def configure(
        self,
        smtp_host: str,
        smtp_port: int,
        smtp_user: str,
        smtp_password: str,
        from_email: str,
    ) -> None:
        """配置 SMTP 服务器"""
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_user = smtp_user
        self._smtp_password = smtp_password
        self._from_email = from_email
        self._enabled = True
        logger.info("邮件服务已配置: %s:%s", smtp_host, smtp_port)

    @property
    def is_available(self) -> bool:
        return self._enabled

    async def send_html_email(
        self,
        to_emails: List[str],
        subject: str,
        html_content: str,
    ) -> bool:
        """
        发送 HTML 邮件

        Args:
            to_emails: 收件人列表
            subject: 邮件主题
            html_content: HTML 格式邮件正文

        Returns:
            是否发送成功
        """
        if not self.is_available:
            logger.warning("邮件服务未配置，跳过发送")
            return False

        if not to_emails:
            logger.warning("收件人列表为空，跳过发送")
            return False

        try:
            import smtplib
            from email.utils import formataddr

            # 创建邮件对象
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = formataddr(("DCIM系统", self._from_email))
            msg["To"] = ", ".join(to_emails)

            # 添加 HTML 内容
            html_part = MIMEText(html_content, "html", "utf-8")
            msg.attach(html_part)

            # 发送邮件
            with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
                server.starttls()
                server.login(self._smtp_user, self._smtp_password)
                server.send_message(msg)

            logger.info("邮件发送成功: to=%s, subject=%s", to_emails, subject)
            return True

        except Exception as e:
            logger.warning("邮件发送失败: %s", e)
            return False


# 全局单例
email_service = EmailService()
