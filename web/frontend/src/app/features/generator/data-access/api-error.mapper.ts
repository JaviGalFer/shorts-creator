import { HttpErrorResponse } from '@angular/common/http';

export interface ApiError {
  code: string;
  message: string;
  status: number;
}

export const UNKNOWN_ERROR_CODE = 'UNKNOWN_ERROR';
export const VALIDATION_ERROR_CODE = 'VALIDATION_ERROR';
export const NETWORK_ERROR_CODE = 'NETWORK_ERROR';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function errorCode(body: unknown): string | null {
  if (!isRecord(body)) {
    return null;
  }
  const error = body['error'];
  if (!isRecord(error)) {
    return null;
  }
  const code = error['code'];
  return typeof code === 'string' && code.length > 0 ? code : null;
}

function errorMessage(body: unknown): string | null {
  if (!isRecord(body)) {
    return null;
  }
  const error = body['error'];
  if (!isRecord(error)) {
    return null;
  }
  const message = error['message'];
  return typeof message === 'string' && message.length > 0 ? message : null;
}

function fallbackCode(status: number): string {
  if (status === 0) {
    return NETWORK_ERROR_CODE;
  }
  if (status === 422) {
    return VALIDATION_ERROR_CODE;
  }
  return UNKNOWN_ERROR_CODE;
}

function fallbackMessage(status: number): string {
  if (status === 0) {
    return 'Could not reach the server.';
  }
  if (status === 422) {
    return 'The request is not valid.';
  }
  return 'Unexpected error.';
}

export function isApiError(value: unknown): value is ApiError {
  return (
    isRecord(value) &&
    typeof value['code'] === 'string' &&
    typeof value['message'] === 'string' &&
    typeof value['status'] === 'number'
  );
}

export function mapApiError(status: number, body: unknown): ApiError {
  return {
    code: errorCode(body) ?? fallbackCode(status),
    message: errorMessage(body) ?? fallbackMessage(status),
    status,
  };
}

export function mapHttpError(error: unknown): ApiError {
  if (isApiError(error)) {
    return error;
  }
  if (error instanceof HttpErrorResponse) {
    return mapApiError(error.status, error.error);
  }
  return mapApiError(0, null);
}
