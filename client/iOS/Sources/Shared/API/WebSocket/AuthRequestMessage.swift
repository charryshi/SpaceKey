import Foundation

class AuthRequestMessage: WebSocketMessage {
    public var AccessToken: String = ""
    public var DevicePublicKey: String?

    private enum CodingKeys: String, CodingKey {
        case AccessToken = "access_token"
        case DevicePublicKey = "device_public_key"
    }

    init(accessToken: String, devicePublicKey: String? = nil) {
        super.init("auth")
        self.ID = nil
        self.AccessToken = accessToken
        self.DevicePublicKey = devicePublicKey
    }

    required init(from decoder: Decoder) throws {
        let values = try decoder.container(keyedBy: CodingKeys.self)
        let superdecoder = try values.superDecoder()
        try super.init(from: superdecoder)

        self.AccessToken = try values.decode(String.self, forKey: .AccessToken)
        self.DevicePublicKey = try values.decodeIfPresent(String.self, forKey: .DevicePublicKey)
    }

    override public func encode(to encoder: Encoder) throws {
        var container = encoder.container(keyedBy: CodingKeys.self)
        try container.encode(AccessToken, forKey: .AccessToken)
        try container.encodeIfPresent(DevicePublicKey, forKey: .DevicePublicKey)

        try super.encode(to: encoder)
    }
}
