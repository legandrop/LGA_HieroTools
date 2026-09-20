# Create Shot: naming interno y acceso vendor

## Por qué existe

En Client, el sufijo de un shot puede representar un vendor externo o el token
interno `SUP`. Confundir ambos crea dos riesgos: un plano externo invisible para
su vendor, o permisos externos aplicados a una prueba interna. Por eso el naming y
el acceso se resuelven por separado y todo el acceso externo es fail-closed.

## Contrato

- `SUP` se compara con trim y sin distinguir mayúsculas. Sirve para reconocer el
  naming interno, pero no forma parte del Shot en Flow:
  `PROJA_010_020_SUP_comp` crea `PROJA_010_020` y la Task `comp`.
- `SUP` nunca recibe `sg_vendor_groups`, `task_assignees` vendor ni altas en
  `Project.users`. Si `vendors[]` contiene `SUP`, se aborta antes de escribir.
- Un vendor externo debe ser exactamente uno, existir en `vendors[]`, tener un
  `vendor_group_ids` válido, un `Group` existente y usuarios no vacíos.
- Cada usuario debe apuntar al mismo Group tanto en `sg_vendor_group` como en el
  campo nativo `HumanUser.groups`. Si una de las dos membresías falta, no se
  escribe nada.
- El Shot nace con `sg_vendor_groups`; cada Task nace con `task_assignees`.
  Los usuarios se agregan a `Project.users` con el modo multi-entidad `add` de
  Flow, sin reenviar ni reemplazar el snapshot de miembros existentes.
- En el diálogo Client, Comp es la única task activa por defecto; CG sigue
  disponible pero apagada. El único reviewer ofrecido es Lega. Los reviewers
  de Studio no se construyen como checkboxes en Client.
- En Client, la familia CG se resuelve por exclusión. Una forma exacta
  `PROJA_010_020_X_stream` trata `X` como candidato vendor aunque `stream` sea
  una disciplina nueva; si `X` no es vendor live ni token interno, se rechaza y
  no se crea `PROJA_010_020_X_stream` como shot largo.
- El catálogo local sólo ayuda a parsear. Si está desactualizado, el candidato se
  valida contra el Project recién leído de Flow; un vendor nuevo puede continuar y
  un token ausente del catálogo live aborta antes de escribir.

Las lecturas de Sequence, Steps, reviewers y acceso vendor forman el preflight.
Después de la primera mutación no se intenta borrar entidades como compensación:
el resultado de la saga identifica IDs, flags y errores como `complete`, `partial`
o `failed` para poder reparar sin perder datos.

## Referencias técnicas

- `LGA_NKS_Shared/LGA_NKS_Flow_NamingUtils.py`: `INTERNAL_VENDOR_TOKEN`,
  `extract_vendor_token()`, `find_unknown_vendor_slot()` y
  `extract_shot_code_with_vendor_candidate()`.
- `LGA_NKS_Shared/LGA_NKS_ClientVendorAccess.py`:
  `resolve_client_vendor_access()`, `resolve_selected_reviewers()`,
  `shot_vendor_fields()`, `task_vendor_fields()` y `add_project_users()`.
- `LGA_NKS_Flow_S3_Panel_py/LGA_NKS_Flow_CreateShot.py`:
  `ShotGridManager.create_shot()` y `CreateShotWorker.run()`.
- `LGA_NKS_Shared/LGA_NKS_AssignmentSaga.py`: resultado parcial, espejo de
  assignees y carga sensible bajo un contexto estable.
