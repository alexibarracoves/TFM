import { Component, OnDestroy } from '@angular/core';
import { MatPaginator, PageEvent } from '@angular/material/paginator';
import { MatTableModule } from '@angular/material/table';
import { MatTableDataSource } from '@angular/material/table';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import {MatButtonModule} from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { DialogoVulnerabilidadesComponent } from '../dialogo-vulnerabilidades/dialogo-vulnerabilidades.component';
import { DialogoLogsComponent } from '../dialogo-logs/dialogo-logs.component';
import { HeaderComponent } from '../header/header.component';

interface Contenedor {
  id: number;
  nombre: string;
  estado: string;
  imagen_id: number;
  imagen_nombre: string;
  capacidades: string;
  puertos: any;
  interfaces: any;
}

@Component({
  selector: 'app-listado-contenedores',
  imports: [
    MatPaginator,
    MatTableModule,
    MatCardModule,
    CommonModule,
    HeaderComponent,
    MatIconModule,
    MatButtonModule
  ],
  templateUrl: './listado-contenedores.component.html',
  styleUrl: './listado-contenedores.component.css'
})
export class ListadoContenedoresComponent implements OnDestroy {
  columnasListado: string[] = ['nombre', 'estado', 'imagen', 'capacidades', 'puertos', 'interfaces', 'resumenLogs'];
  dataSource = new MatTableDataSource<Contenedor>([]);
  pageSize = 10;
  totalPages = 0;
  totalItems = 0;
  currentPage = 0;
  modo = '';
  mostrarCapacidades = false;

  private refreshInterval: any;

  constructor(private http: HttpClient, private dialog: MatDialog) {}

  ngOnInit(): void {
    this.loadContenedores(this.currentPage, this.pageSize);

    this.refreshInterval = setInterval(() => {
      this.loadContenedores(this.currentPage, this.pageSize);
    }, 2500);
  }

  ngOnDestroy(): void {
    if (this.refreshInterval) {
      clearInterval(this.refreshInterval);
    }
  }

  loadContenedores(page: number, size: number) {
    this.http.get<any>(`http://localhost:3000/contenedores?page=${page}&size=${size}`).subscribe(res => {
      this.dataSource.data = res.data;
      this.totalPages = res.totalPages;
      this.totalItems = res.totalItems
      this.modo = res.podmanMode;
    });
  }

  onPaginateChange(event: PageEvent) {
    this.currentPage = event.pageIndex;
    this.pageSize = event.pageSize;
    this.loadContenedores(event.pageIndex, event.pageSize);
  }

  baselineCaps = new Set([
    'CAP_CHOWN', 'CAP_DAC_OVERRIDE', 'CAP_FOWNER', 'CAP_FSETID',
    'CAP_KILL', 'CAP_NET_BIND_SERVICE', 'CAP_SETFCAP', 'CAP_SETGID',
    'CAP_SETPCAP', 'CAP_SETUID', 'CAP_SYS_CHROOT'
  ]);
  
  isBaseline(cap: string): boolean {
    return this.baselineCaps.has(cap);
  }

  objectKeys(obj: any): string[] {
    return Object.keys(obj);
  }

  getInterfaceProperty(interfaceData: any, property: string): string | null {
    if (interfaceData && interfaceData[property]) {
      return interfaceData[property];
    }
    return null;
  }

  abrirDialogo(idImagen: number, imagen: string): void {
    this.dialog.open(DialogoVulnerabilidadesComponent, {
      maxWidth: '100vw',
      maxHeight: '100vh',
      height: '65vh',
      width: '80%',
      data: { idImagen, imagen }
    });
  }

  abrirAnalisisLogs(nombreContenedor: number): void {
    this.dialog.open(DialogoLogsComponent, {
      maxWidth: '100vw',
      maxHeight: '100vh',
      height: 'auto',
      width: '80%',
      data: { nombreContenedor }
    });
  }

  onMostrarCapacidadesChange(valor: boolean) {
    this.mostrarCapacidades = valor;
  }
}
