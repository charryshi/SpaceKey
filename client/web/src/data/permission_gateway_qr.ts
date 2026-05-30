export const parsePermissionGatewayQrId = (
  value: string
): string | undefined => {
  const trimmed = value.trim();
  if (!trimmed) {
    return undefined;
  }

  try {
    const parsed = JSON.parse(trimmed);
    const qrId = parsed.qr_id || parsed.qrId || parsed.template_id;
    if (typeof qrId === "string" && qrId.trim()) {
      return qrId.trim();
    }
  } catch (_err: any) {
    // Not JSON, continue with URL/plain parsing.
  }

  try {
    const url = new URL(trimmed);
    const qrId =
      url.searchParams.get("qr_id") ||
      url.searchParams.get("qrId") ||
      url.searchParams.get("template_id");
    if (qrId?.trim()) {
      return qrId.trim();
    }
  } catch (_err: any) {
    // Not a URL, treat as a raw activation code.
  }

  return trimmed;
};
