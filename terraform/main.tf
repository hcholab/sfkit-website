terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 7.25.0"
    }
  }

  backend "gcs" {
    prefix = "sfkit-website"
  }
}

provider "google" {
  project = var.project_id
}

data "google_project" "current" {}

resource "google_project_service" "apis" {
  for_each = toset([
    "artifactregistry.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "compute.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "secretmanager.googleapis.com",
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

resource "google_secret_manager_secret" "firebase_api_key" {
  secret_id = "FIREBASE_API_KEY"

  replication {
    auto {}
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

resource "google_secret_manager_secret_iam_member" "cloud_run_secret" {
  secret_id = google_secret_manager_secret.firebase_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.sa_member
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
        name  = "SFKIT_API_URL"
        value = "https://${var.service_name}-${data.google_project.current.number}.${var.service_region}.run.app/api"
      }
      env {
        name  = "SERVER_GCP_PROJECT"
        value = var.project_id
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
    google_secret_manager_secret_iam_member.cloud_run_secret,
    google_service_account_iam_member.cloud_run_token_creator
  ]
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

resource "google_firebaserules_ruleset" "firestore" {
  project = var.project_id

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
          }
        }
      EOT
    }
  }

  depends_on = [
    google_firestore_database.db
  ]
}

resource "google_firebaserules_release" "firestore" {
  project      = var.project_id
  name         = var.database_name == "(default)" ? "cloud.firestore" : "cloud.firestore/${var.database_name}"
  ruleset_name = google_firebaserules_ruleset.firestore.name
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
