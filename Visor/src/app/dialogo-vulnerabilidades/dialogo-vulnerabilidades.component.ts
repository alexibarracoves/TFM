import { Component, Inject } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogRef, MatDialogModule, MatDialogContent, MatDialogTitle } from '@angular/material/dialog';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { CommonModule } from '@angular/common';
import { MatTableModule } from '@angular/material/table';
import { HttpClient } from '@angular/common/http';
import { MatTableDataSource } from '@angular/material/table';

interface Vulnerabilidad {
  vulnerabilidad: string;
  libreria: string;
  severidad: string;
  estado: string;
  version: string;
  informacion: string;
  enlace: string;
}

interface Imagen {
  id: number;
  nombre: string;
  hash: string;
  numero_desconocida: number;
  numero_baja: number;
  numero_media: number; 
  numero_alta: number;
  numero_critica: number;
}

@Component({
  selector: 'app-dialogo-vulnerabilidades',
  imports: [
    MatTableModule,
    CommonModule,
    MatDialogContent,
    MatDialogTitle,
    MatPaginator,
    MatDialogModule
  ],
  templateUrl: './dialogo-vulnerabilidades.component.html',
  styleUrl: './dialogo-vulnerabilidades.component.css'
})
export class DialogoVulnerabilidadesComponent {
  columnasListado: string[] = ['vulnerabilidad', 'libreria', 'severidad', 'estado', 'version', 'informacion'];
  dataSource = new MatTableDataSource<Vulnerabilidad>([]);
  imagen: Imagen = {
    id: 0,
    nombre: '',
    hash: '',
    numero_desconocida: 0,
    numero_baja: 0,
    numero_media: 0,
    numero_alta: 0,
    numero_critica: 0
  };
  pageSize = 5;
  totalPages = 0;
  totalItems = 0;
  currentPage = 0;

  constructor(
    public dialogRef: MatDialogRef<DialogoVulnerabilidadesComponent>,
    @Inject(MAT_DIALOG_DATA) public data: { idImagen: number, imagen: string  },
    private http: HttpClient
  ) {}

  ngOnInit(): void {
    this.loadImagen();
    this.loadVulnerabilidades(this.currentPage ,this.pageSize);
  }

  loadVulnerabilidades(page: number, size: number) {
    this.http.get<any>(`http://localhost:3000/vulnerabilidades/${this.data.idImagen}?page=${page}&size=${size}`).subscribe(res => {
      this.dataSource.data = res.data;
      this.totalPages = res.totalPages;
      this.totalItems = res.totalItems;
    });
  }

  loadImagen(){
    this.http.get<any>(`http://localhost:3000/imagenes/${this.data.idImagen}`).subscribe(res => {
      this.imagen = res;
    });
  }

  onPaginateChange(event: PageEvent) {
    this.currentPage = event.pageIndex;
    this.pageSize = event.pageSize;
    this.loadVulnerabilidades(event.pageIndex, event.pageSize);
  }

  estiloSeveridad(severidad: string): string {
    switch (severidad) {
      case 'Media':
        return 'amarillo';
      case 'Alta':
        return 'naranja';
      case 'Crítica':
        return 'rojo';
      default:
        return '';
    }
  }

}
