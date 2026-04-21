terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.25.0"
    }
    google-beta = {
      source  = "hashicorp/google-beta"
      version = "~> 7.25.0"
    }
  }

  backend "gcs" {
    prefix = "sfkit-website"
  }
}

provider "google" {
  project               = var.project_id
  billing_project       = var.project_id
  user_project_override = true
}

provider "google-beta" {
  project               = var.project_id
  billing_project       = var.project_id
  user_project_override = true
}

data "google_project" "current" {}

resource "google_project_service" "apis" {
  for_each = toset([
    "apikeys.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "firebase.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "run.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "results" {
  name                        = var.results_bucket
  location                    = var.storage_region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  depends_on = [google_project_service.apis]
}

resource "google_firebase_web_app" "firebase" {
  provider     = google-beta
  project      = var.project_id
  display_name = var.service_name
  api_key_id   = google_apikeys_key.sfkit.uid
  depends_on   = [google_project_service.apis]
}

data "google_firebase_web_app_config" "firebase" {
  provider   = google-beta
  web_app_id = google_firebase_web_app.firebase.app_id
}

resource "google_apikeys_key" "sfkit" {
  project      = var.project_id
  name         = "sfkit-firebase"
  display_name = "Sfkit Firebase API key"

  restrictions {
    browser_key_restrictions {
      allowed_referrers = split(",", var.cors_origins)
    }
    api_targets {
      service = "firestore.googleapis.com"
    }
    api_targets {
      service = "identitytoolkit.googleapis.com"
    }
  }
  depends_on = [google_project_service.apis]
}

resource "google_service_account" "cloud_run" {
  account_id   = "${var.service_name}-sa"
  display_name = "Service Account for ${var.service_name} Cloud Run"

  depends_on = [google_project_service.apis]
}

locals {
  sa_member = "serviceAccount:${google_service_account.cloud_run.email}"
}

resource "google_project_iam_custom_role" "sfkit_compute" {
  project     = var.project_id
  role_id     = "sfkitCompute"
  title       = "sfkit Compute Manager"
  description = "Minimal Compute Engine permissions required by sfkit-website to manage P0 VMs and networking"
  permissions = [
    "compute.disks.create",
    "compute.firewalls.create",
    "compute.firewalls.delete",
    "compute.firewalls.list",
    "compute.globalOperations.get",
    "compute.instances.create",
    "compute.instances.delete",
    "compute.instances.get",
    "compute.instances.list",
    "compute.instances.setMetadata",
    "compute.instances.setServiceAccount",
    "compute.instances.setTags",
    "compute.instances.stop",
    "compute.networks.addPeering",
    "compute.networks.create",
    "compute.networks.delete",
    "compute.networks.get",
    "compute.networks.list",
    "compute.networks.removePeering",
    "compute.regionOperations.get",
    "compute.subnetworks.create",
    "compute.subnetworks.delete",
    "compute.subnetworks.list",
    "compute.subnetworks.use",
    "compute.subnetworks.useExternalIp",
    "compute.zoneOperations.get",
  ]
}

resource "google_project_iam_member" "cloud_run_compute" {
  project = var.project_id
  role    = google_project_iam_custom_role.sfkit_compute.name
  member  = local.sa_member
}

resource "google_project_iam_member" "cloud_run_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = local.sa_member
}

resource "google_storage_bucket_iam_member" "cloud_run_bucket" {
  bucket = google_storage_bucket.results.name
  role   = "roles/storage.objectUser"
  member = local.sa_member
}

resource "google_service_account_iam_member" "cloud_run_token_creator" {
  service_account_id = google_service_account.cloud_run.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = local.sa_member
}

resource "google_cloud_run_v2_service" "website" {
  name     = var.service_name
  location = var.service_region

  template {
    service_account = google_service_account.cloud_run.email

    containers {
      image = var.image

      env {
        name  = "CLOUD_RUN"
        value = "True"
      }
      env {
        name  = "CORS_ORIGINS"
        value = var.cors_origins
      }
      env {
        name  = "FLASK_DEBUG"
        value = var.flask_debug
      }
      env {
        name  = "FIRESTORE_DATABASE"
        value = google_firestore_database.db.name
      }
      env {
        name  = "FIREBASE_API_KEY"
        value = data.google_firebase_web_app_config.firebase.api_key
      }
      env {
        name  = "SFKIT_API_URL"
        value = "https://${var.service_name}-${data.google_project.current.number}.${var.service_region}.run.app/api"
      }
      env {
        name  = "SERVER_GCP_PROJECT"
        value = var.project_id
      }
      env {
        name  = "SFKIT_P0_SERVICE_ACCOUNT"
        value = google_service_account.p0_vm.email
      }
      env {
        name  = "RESULTS_BUCKET"
        value = google_storage_bucket.results.name
      }
      env {
        name  = "OIDC_AUDIENCE"
        value = var.oidc_audience
      }
      env {
        name  = "OIDC_JWKS_URL"
        value = var.oidc_jwks_url
      }
    }
  }

  depends_on = [
    google_project_iam_member.cloud_run_firestore,
    google_storage_bucket_iam_member.cloud_run_bucket,
    google_service_account_iam_member.cloud_run_token_creator
  ]
}

locals {
  p0_vm_member = "serviceAccount:${google_service_account.p0_vm.email}"
}

resource "google_service_account" "p0_vm" {
  account_id   = "${var.service_name}-p0"
  display_name = "Service Account for ${var.service_name} P0 VMs"

  depends_on = [google_project_service.apis]
}

resource "google_storage_bucket_iam_member" "p0_vm_results_reader" {
  bucket = google_storage_bucket.results.name
  role   = "roles/storage.objectViewer"
  member = local.p0_vm_member
}

resource "google_project_iam_member" "p0_vm_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = local.p0_vm_member
}

resource "google_service_account_iam_member" "cloud_run_p0_vm_sa_user" {
  service_account_id = google_service_account.p0_vm.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.sa_member
}

resource "google_service_account" "frontend" {
  account_id   = "${var.frontend_service_name}-sa"
  display_name = "Service Account for ${var.frontend_service_name} Cloud Run"

  depends_on = [google_project_service.apis]
}

# Firestore

resource "google_firestore_database" "db" {
  name        = var.database_name
  location_id = var.database_region
  type        = "FIRESTORE_NATIVE"

  delete_protection_state = "DELETE_PROTECTION_ENABLED"

  depends_on = [google_project_service.apis]
}

locals {
  firebaserules_release = var.database_name == "(default)" ? "cloud.firestore" : "cloud.firestore/${var.database_name}"
}

import {
  to = google_firebaserules_release.firestore
  id = "projects/${var.project_id}/releases/${local.firebaserules_release}"
}

resource "google_firebaserules_release" "firestore" {
  project      = var.project_id
  name         = local.firebaserules_release
  ruleset_name = google_firebaserules_ruleset.firestore.name
}

resource "google_firebaserules_ruleset" "firestore" {
  source {
    files {
      name    = "firestore.rules"
      content = <<-EOT
        rules_version = '2';
        service cloud.firestore {
          match /databases/{database}/documents {
            match /users/{userId} {
              allow read: if request.auth.uid == userId;
            }
            match /users/display_names {
              allow read: if request.auth != null;
            }
            match /studies/{studyId} {
              allow read: if request.auth.uid in resource.data.participants;
            }
          }
        }
      EOT
    }
  }

  depends_on = [
    google_firestore_database.db
  ]
}

# Artifact Registry

import {
  to = google_artifact_registry_repository.docker
  id = "projects/${var.project_id}/locations/us/repositories/${var.artifact_repository}"
}

resource "google_artifact_registry_repository" "docker" {
  location               = "us"
  repository_id          = var.artifact_repository
  format                 = "DOCKER"
  cleanup_policy_dry_run = true

  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 10
    }
  }

  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"
    condition {
      tag_state  = "TAGGED"
      older_than = "30d"
    }
  }

  cleanup_policies {
    id     = "delete-untagged"
    action = "DELETE"
    condition {
      tag_state = "UNTAGGED"
    }
  }
}
