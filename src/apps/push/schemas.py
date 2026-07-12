from ninja import Schema


class PushKeysSchema(Schema):
    p256dh: str
    auth: str


class SubscribeSchema(Schema):
    """The browser's PushSubscription.toJSON() shape."""

    endpoint: str
    keys: PushKeysSchema


class UnsubscribeSchema(Schema):
    endpoint: str


class VapidKeySchema(Schema):
    vapid_public_key: str
