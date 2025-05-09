import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DialogoVulnerabilidadesComponent } from './dialogo-vulnerabilidades.component';

describe('DialogoVulnerabilidadesComponent', () => {
  let component: DialogoVulnerabilidadesComponent;
  let fixture: ComponentFixture<DialogoVulnerabilidadesComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DialogoVulnerabilidadesComponent]
    })
    .compileComponents();

    fixture = TestBed.createComponent(DialogoVulnerabilidadesComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
