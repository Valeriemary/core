"""Constants for the imap integration."""

from typing import Final

DOMAIN: Final = "imap"

CONF_SERVER: Final = "server"
CONF_FOLDER: Final = "folder"
CONF_SEARCH: Final = "search"
CONF_CHARSET: Final = "charset"
CONF_MAX_MESSAGE_SIZE = "max_message_size"
CONF_SSL_CIPHER_LIST: Final = "ssl_cipher_list"

DEFAULT_PORT: Final = 993

DEFAULT_MAX_MESSAGE_SIZE = 2048

MAX_MESSAGE_SIZE_LIMIT = 30000
