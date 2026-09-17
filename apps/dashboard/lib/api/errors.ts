export type ApiErrorPayload = { code: string; message: string; requestId?: string; details?: unknown };

export class ApiError extends Error {
  readonly code: string;
  readonly requestId?: string;
  readonly details?: unknown;
  readonly status: number;

  constructor(status: number, payload: ApiErrorPayload) {
    super(payload.message);
    this.name = "ApiError";
    this.status = status;
    this.code = payload.code;
    this.requestId = payload.requestId;
    this.details = payload.details;
  }
}
