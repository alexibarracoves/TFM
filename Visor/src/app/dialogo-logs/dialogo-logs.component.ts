import { Component, Inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MAT_DIALOG_DATA, MatDialogRef, MatDialogContent, MatDialogTitle } from '@angular/material/dialog';

@Component({
  selector: 'app-dialogo-logs',
  imports: [
    CommonModule,
    MatDialogContent,
    MatDialogTitle,
  ],
  templateUrl: './dialogo-logs.component.html',
  styleUrl: './dialogo-logs.component.css'
})
export class DialogoLogsComponent {

  constructor(
    public dialogRef: MatDialogRef<DialogoLogsComponent>,
    @Inject(MAT_DIALOG_DATA) public data: { nombreContenedor: string }
  ) {}

}
