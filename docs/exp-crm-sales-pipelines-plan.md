# EXP CRM Sales Pipelines

This document describes the sales pipeline architecture implemented in the EXP
CRM fork, its migration and import contracts, and its operational limits. It
replaces the original implementation checklist; past local test results are not
release evidence.

## Product Model

Leads are a shared intake and qualification workspace. Their `status` remains
global; source, owner, filters and saved views provide segmentation. The optional
`planned_deal_pipeline` routes future conversion without creating a second sales
pipeline system for leads.

Deals belong to independent sales pipelines with their own stages. Pipeline
configuration belongs to each site, not to customer-specific code. For example,
a site may use B2C, B2B and agency pipelines with different sales processes.

Converted leads retain the existing behavior: conversion sets `converted = 1`,
sets `Qualified` when that status exists, creates or links Contact and
Organization, creates the deal, and redirects to it. Active lead views keep
`converted = 0`, so the same opportunity does not remain in both active workspaces.
Normal lead permissions and SLA communication-status handling still apply.

## Data Model

### CRM Sales Pipeline

Main fields:

```text
pipeline_name
enabled
is_default
position
color
icon
description
archived
enable_kanban_freeze_effect
```

Exactly one enabled default pipeline is selected. The default cannot be archived
or disabled, and at least one pipeline must stay active. Archiving preserves
existing deals and history.

The pipeline also owns transition rules and external mapping fields described
below. It applies to deals; leads only carry an optional planned pipeline.

### CRM Deal Status

Stages reuse `CRM Deal Status`, so existing status links, forecasting,
probabilities, lost-reason handling and status-change logs keep their existing
DocType contract.

```text
name: stable technical ID
deal_status: visible stage title
pipeline: Link to CRM Sales Pipeline
type: Open / Ongoing / On Hold / Won / Lost
probability
color
position
archived
```

New records use generated names (`CRM-DEAL-STAGE-{#####}`). Migration preserves
existing names. Visible titles are unique within a pipeline, rather than globally:
`Quote` in B2C and `Quote` in B2B are distinct stages. UI controls display
`deal_status`, while stored links use the technical name.

There is no per-stage `is_default` flag. Default stage selection uses type and
position: first an active Open stage, then Ongoing/On Hold, then any active stage.
A pipeline without a usable stage fails deal validation.

### CRM Deal and CRM Lead

`CRM Deal.pipeline` is required and `CRM Deal.status` remains a Link to
`CRM Deal Status`.

- Missing pipeline is inferred from an explicit stage, otherwise from the default
  enabled pipeline.
- Missing status is selected using the pipeline's default-stage algorithm.
- If only pipeline changes and the previous stage belongs elsewhere, the status
  is reset. An explicitly supplied mismatched stage is rejected.
- Archived pipelines cannot be used for a deal save.
- Won/Lost behavior continues to use the stage's `type`; lost-reason validation
  remains in force.

`CRM Lead.planned_deal_pipeline` is optional. Convert to Deal preselects it when
present, otherwise the default enabled pipeline. The user may choose another
pipeline; the stage options/default follow that choice. Import, API and forms
must all obey backend pipeline/stage validation; frontend filtering alone is
insufficient.

## Kanban, Forms and Settings

Leads keep one status-based kanban and can use source or planned pipeline as
filters. Deals show a pipeline selector and constrain list/group/kanban results
and status columns to that pipeline. The last selected pipeline is stored in the
browser and reused on return, with the default enabled pipeline as fallback.

Kanban columns display stage titles and write technical stage names. Dragging a
card changes stage within the selected pipeline. Creating from a column
preselects both pipeline and stage; creating from the Deals page preselects the
pipeline. Generic add/delete/reorder-column controls are hidden for pipeline
kanban: stage management belongs to Sales Pipelines settings. Saved views may
include the pipeline filter.

Deal quick entry, detail/mobile forms and Convert to Deal share pipeline-aware
stage options. Default field layouts receive `pipeline` and
`planned_deal_pipeline` idempotently; customized layouts are preserved.

Open **Settings → Sales Pipelines**. The API permits Sales Managers and System
Managers. The first screen lists pipelines with default/disabled/archived state
and counts; opening one shows the full-width editor. The editor supports:

- Creating, renaming, ordering, enabling/disabling, archiving/restoring and
  duplicating pipelines, and choosing the default.
- Creating and editing stages, type, probability, color and position, and
  ordering or archiving/restoring stages.
- Configuring transition rules.

Archive actions require confirmation. Archiving a pipeline or active stage with
active deals requires moving those deals first, or a confirmed force operation
by Administrator/System Manager. Duplication copies active stages and pipeline
settings, including transition rules. Technical API/DocType names remain stable
when user-visible labels are translated.

## Transition Rules

Each pipeline exposes three independent rules:

- `stage_skip_rule`: moving forward over intermediate stages.
- `stage_backwards_rule`: moving to an earlier stage.
- `closing_fields_rule`: moving to Won/Lost without fields listed in
  `required_fields_before_closing`.

Each accepts `Allow`, `Warn` or `Block`. `Warn` saves and displays a warning;
`Block` raises a backend validation error. Legacy boolean fields
`warn_on_stage_skip`, `warn_on_stage_backwards` and
`warn_on_closing_without_required_fields` remain a fallback when a valid mode is
absent. The migration maps those booleans to explicit modes.

These rules check changes on existing deals with a prior stage in the selected
pipeline. They do not replace pipeline/stage or lost-reason validation, and are
not an approval workflow or a per-role transition policy.

## Import and External Identity

For technical imports use `pipeline` and `status` with stored document IDs.
For human-authored CSV use the hidden helper fields `pipeline_label` and
`status_label`; these resolve before validation and are cleared after use.
Labels are resolved within the selected pipeline. An ambiguous stage title
without pipeline context is rejected.

For repeatable imports provide `external_source` with the relevant external IDs:

| CRM record     | External fields                                                    |
| -------------- | ------------------------------------------------------------------ |
| Sales pipeline | `external_pipeline_id`                                             |
| Stage          | `external_status_id`, `external_pipeline_id`                       |
| Deal           | `external_record_id`, `external_pipeline_id`, `external_status_id` |

External IDs require `external_source`. Explicit technical IDs, labels and
external IDs must agree; mismatches fail instead of silently choosing one input.
Deal external record IDs are unique within an external source. Stage external
IDs are scoped to their pipeline.

`CRM External Reference` stores mappings by external source, external object
type, external ID and optional external parent ID. It supports several external
sources pointing to one CRM record; the scalar import fields remain compatibility
inputs. Duplicate or conflicting bindings fail validation. Re-import callers
must resolve existing identity before deciding to create a record; these fields
are not a general automatic merge policy.

For amoCRM/Kommo migration, pipelines map to `CRM Sales Pipeline`, statuses to
`CRM Deal Status`, and sales opportunities called "leads" there normally map to
`CRM Deal`. Only raw inquiries should become CRM Leads. Simple one-time CSV may
use labels; repeatable imports should retain external identity for deduplication
and troubleshooting.

## Migration on Another Site

Migration patches and helpers live in `crm/patches/v1_0`:

- `setup_sales_pipelines` creates the default pipeline and associates existing
  statuses/deals without replacing their stored names or deleting statuses.
- `add_sales_pipeline_fields_to_layouts` adds fields to default layouts without
  overwriting customized layouts.
- `add_sales_pipeline_rule_fields` and `add_sales_pipeline_rule_modes` add rule
  configuration and map legacy warning booleans to modes.
- `backfill_crm_external_references` creates scoped mappings from existing
  import fields.

Default seed labels remain canonical English values regardless of locale
(`Default Deal Pipeline`, `Qualification`, `Demo/Making`, `Proposal/Quotation`,
`Negotiation`, `Ready to Close`, `Won`, `Lost`). UI translations provide localized
labels; migration must not rename customer pipelines/stages or linked records
for localization. Existing leads need no planned pipeline unless one is set.

Run from the bench directory against a disposable test site with the fork's
required applications installed. Verify both a clean installation and migration
of a copy of existing data, followed by a repeated migrate. Do not run integration
tests against a production database.

```bash
bench --site <test-site> migrate
bench --site <test-site> run-tests --module crm.fcrm.doctype.crm_sales_pipeline.test_crm_sales_pipeline --test-category all
bench --site <test-site> run-tests --module crm.fcrm.doctype.crm_deal_status.test_crm_deal_status --test-category all
bench --site <test-site> run-tests --module crm.fcrm.doctype.crm_deal.test_crm_deal --test-category all
bench --site <test-site> run-tests --module crm.fcrm.doctype.crm_lead.test_crm_lead --test-category all
bench --site <test-site> run-tests --module crm.fcrm.doctype.crm_external_reference.test_crm_external_reference --test-category all
```

From `apps/crm/frontend`, run `yarn test:run` and `yarn build`.

The CRM Lead and CRM Deal modules use `IntegrationTestCase`, create real Frappe
documents, and run Frappe's fixture setup. Check required application fixtures
when setup fails before a test executes; such a failure does not verify the
pipeline scenario. A successful isolated test run also does not replace UI checks.

## Maintenance and Acceptance Checks

Keep pipeline logic in focused helpers and shared components. Avoid duplicating
the kanban system or relying only on UI validation. Upstream-sensitive areas
include Deals/Deal/Lead pages, create/convert modals, ViewControls/KanbanView,
status stores, `crm/api/doc.py`, and CRM Lead/Deal controllers. Review these
paths when merging an upstream update, then test/build and migrate a separate
site before deployment. Apply the fork's requirements and preserve customized
site data.

The settings UI uses `crm.api.sales_pipeline` for reads, saves, duplication,
archiving and ordering. Pipeline/stage controllers enforce identities and
validation; `CRM Deal` enforces transition rules; lead conversion supplies the
chosen pipeline. Status APIs/stores must keep technical values distinct from
visible labels.

For acceptance, verify existing data survives migration; independent pipelines
show only their stages; kanban cannot assign a stage from another pipeline;
create/edit/convert forms share defaults; converted leads leave active lead
views; archive/restore preserves records; and required access checks apply.
Check import ambiguity, conflicting identity, repeat import and transition rules
through backend APIs as well as through the UI.

## Known Limits

- Leads retain global qualification statuses; `planned_deal_pipeline` only routes
  conversion.
- Pipeline-specific field layouts, approval workflows and role-specific stage
  restrictions are outside the implemented transition rules.
- Reporting must use stable stage IDs and include pipeline context where visible
  titles repeat. Do not aggregate unrelated stages solely by title; verify
  pipeline filters and stage probabilities for each report.
- Import mapping is source-neutral. Provider-specific history import or automatic
  reconciliation requires its own documented contract and validation.
