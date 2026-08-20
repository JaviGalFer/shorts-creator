import { HttpErrorResponse } from '@angular/common/http';
import { describe, expect, it } from 'vitest';

import { mapApiError, mapHttpError } from './api-error.mapper';

describe('api-error mapper', () => {
  it('maps a structured {error:{code,message}} body', () => {
    const error = mapApiError(404, { error: { code: 'JOB_NOT_FOUND', message: 'Job not found.' } });
    expect(error).toEqual({ code: 'JOB_NOT_FOUND', message: 'Job not found.', status: 404 });
  });

  it('maps a 409 busy error', () => {
    const error = mapApiError(409, { error: { code: 'JOB_EXECUTION_BUSY', message: 'Busy.' } });
    expect(error.code).toBe('JOB_EXECUTION_BUSY');
    expect(error.status).toBe(409);
  });

  it('falls back to VALIDATION_ERROR for a 422 body without structured error', () => {
    const error = mapApiError(422, { detail: [{ loc: ['body'], msg: 'field required' }] });
    expect(error.code).toBe('VALIDATION_ERROR');
    expect(error.status).toBe(422);
    expect(error.message).toBeTruthy();
  });

  it('falls back to NETWORK_ERROR for status 0', () => {
    const error = mapApiError(0, null);
    expect(error.code).toBe('NETWORK_ERROR');
    expect(error.status).toBe(0);
  });

  it('falls back to UNKNOWN_ERROR for a non-structured body', () => {
    const error = mapApiError(500, 'not json');
    expect(error.code).toBe('UNKNOWN_ERROR');
    expect(error.status).toBe(500);
  });

  it('does not leak a raw error object as message', () => {
    const error = mapApiError(500, { error: 'Traceback (most recent call last): ...' });
    expect(error.message).not.toContain('Traceback');
  });

  it('maps an HttpErrorResponse via mapHttpError', () => {
    const httpError = new HttpErrorResponse({
      status: 404,
      statusText: 'Not Found',
      error: { error: { code: 'JOB_NOT_FOUND', message: 'Job not found.' } },
    });
    const error = mapHttpError(httpError);
    expect(error.code).toBe('JOB_NOT_FOUND');
    expect(error.status).toBe(404);
  });

  it('is idempotent for an already-mapped ApiError', () => {
    const alreadyMapped = { code: 'JOB_EXECUTION_BUSY', message: 'Busy.', status: 409 };
    expect(mapHttpError(alreadyMapped)).toBe(alreadyMapped);
  });

  it('maps an unknown non-Http error to NETWORK_ERROR', () => {
    const error = mapHttpError(new Error('boom'));
    expect(error.code).toBe('NETWORK_ERROR');
    expect(error.status).toBe(0);
  });
});
