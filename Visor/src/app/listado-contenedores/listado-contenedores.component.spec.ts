import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ListadoContenedoresComponent } from './listado-contenedores.component';

describe('ListadoContenedoresComponent', () => {
  let component: ListadoContenedoresComponent;
  let fixture: ComponentFixture<ListadoContenedoresComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ListadoContenedoresComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ListadoContenedoresComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
