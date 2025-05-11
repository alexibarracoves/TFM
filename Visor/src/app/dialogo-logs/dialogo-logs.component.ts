import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MAT_DIALOG_DATA, MatDialogRef, MatDialogContent, MatDialogTitle } from '@angular/material/dialog';
import { HttpClient } from '@angular/common/http';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

@Component({
  selector: 'app-dialogo-logs',
  imports: [
    CommonModule,
    MatDialogContent,
    MatDialogTitle,
    MatProgressSpinnerModule
  ],
  templateUrl: './dialogo-logs.component.html',
  styleUrl: './dialogo-logs.component.css'
})
export class DialogoLogsComponent {
  resumen: string = '';
  loading: boolean = true;
  error: boolean = false;

  constructor(
    public dialogRef: MatDialogRef<DialogoLogsComponent>,
    @Inject(MAT_DIALOG_DATA) public data: { nombreContenedor: string },
    private http: HttpClient
  ) {}

  ngOnInit(): void {
    this.http.get<any>(`http://localhost:3000/contenedores/${this.data.nombreContenedor}/logs/resumen`)
      .subscribe({
        next: (res) => {
          this.resumen = res.resumen;
          this.loading = false;
        },
        error: () => {
          this.resumen = 'Error al analizar los logs.';
          this.loading = false;
          this.error = true;
        }
      });
  }

}