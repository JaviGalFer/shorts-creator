import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, catchError, throwError } from 'rxjs';

import { mapHttpError } from './api-error.mapper';
import type {
  CapabilitiesDto,
  CreateJobRequestDto,
  JobListResponseDto,
  JobResponseDto,
} from './shorts-api.dto';

const API_BASE_URL = '/api/v1';

@Injectable({ providedIn: 'root' })
export class ShortsApiClient {
  private readonly http = inject(HttpClient);

  getCapabilities(): Observable<CapabilitiesDto> {
    return this.http
      .get<CapabilitiesDto>(`${API_BASE_URL}/capabilities`)
      .pipe(catchError((error) => throwError(() => mapHttpError(error))));
  }

  createJob(request: CreateJobRequestDto): Observable<JobResponseDto> {
    return this.http
      .post<JobResponseDto>(`${API_BASE_URL}/jobs`, request)
      .pipe(catchError((error) => throwError(() => mapHttpError(error))));
  }

  getJob(jobId: string): Observable<JobResponseDto> {
    return this.http
      .get<JobResponseDto>(`${API_BASE_URL}/jobs/${jobId}`)
      .pipe(catchError((error) => throwError(() => mapHttpError(error))));
  }

  listJobs(): Observable<JobListResponseDto> {
    return this.http
      .get<JobListResponseDto>(`${API_BASE_URL}/jobs`)
      .pipe(catchError((error) => throwError(() => mapHttpError(error))));
  }

  videoUrl(jobId: string): string {
    return `${API_BASE_URL}/jobs/${jobId}/video`;
  }

  downloadUrl(jobId: string): string {
    return `${API_BASE_URL}/jobs/${jobId}/download`;
  }
}
