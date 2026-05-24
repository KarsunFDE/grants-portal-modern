import { Component, OnInit } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { GrantApplication } from '../../models/grant-application';

/**
 * GrantApplication list view.
 *
 * ⚠ DELIBERATE BROWNFIELD DEBT — Item 8 in docs/brownfield-debt.md ⚠
 *
 * This component hardcodes `http://localhost:8081/api/grant-applications` —
 * bypassing the API gateway at :8080. Compare with
 * {@link ../../services/grant-application.service.ts} which uses
 * `environment.apiGatewayUrl`.
 *
 * The hardcode was introduced "temporarily" by a developer who couldn't
 * get the gateway running locally and was never reverted. Cohort fixes
 * in W4 Tue API modernization patterns.
 */
@Component({
  selector: 'app-grant-application-list',
  standalone: true,
  imports: [CommonModule, RouterLink],
  template: `
    <h2>GrantApplications</h2>
    <p>
      <a routerLink-grant-applications/new"><button>+ New grantApplication</button></a>
    </p>
    <div *ngIf="loading">Loading…</div>
    <div *ngIf="error" style="color: crimson">{{ error }}</div>
    <table *ngIf="!loading && !error">
      <thead>
        <tr><th>Title</th><th>Agency</th><th>Status</th><th>ID</th></tr>
      </thead>
      <tbody>
        <tr *ngFor="let s of grantApplications">
          <td>{{ s.title }}</td>
          <td>{{ s.agencyId }}</td>
          <td>{{ s.status }}</td>
          <td><code>{{ s.id }}</code></td>
        </tr>
        <tr *ngIf="grantApplications.length === 0">
          <td colspan="4"><em>No grantApplications yet. Create one!</em></td>
        </tr>
      </tbody>
    </table>
  `,
})
export class GrantApplicationListComponent implements OnInit {
  // ⚠ Item 8 — hardcoded URL bypasses the API gateway at :8080.
  private apiUrl = 'http://localhost:8081/api/grant-applications';

  grantApplications: GrantApplication[] = [];
  loading = true;
  error: string | null = null;

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.http.get<GrantApplication[]>(this.apiUrl).subscribe({
      next: (data) => {
        this.grantApplications = data || [];
        this.loading = false;
      },
      error: (err) => {
        this.error = `Failed to load grantApplications: ${err.message ?? err}`;
        this.loading = false;
      },
    });
  }
}
