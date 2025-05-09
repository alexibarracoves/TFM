import { Component } from '@angular/core';
import { ListadoContenedoresComponent } from './listado-contenedores/listado-contenedores.component';


@Component({
  selector: 'app-root',
  imports: [
    ListadoContenedoresComponent
  ],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})
export class AppComponent {
  title = 'Visor';
}