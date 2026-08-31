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
    "firebaserules.googleapis.com",
    "firestore.googleapis.com",
    "iam.googleapis.com",
    "identitytoolkit.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
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

resource "google_firebase_project" "firebase" {
  provider   = google-beta
  depends_on = [google_project_service.apis]
}

resource "google_firebase_web_app" "firebase" {
  provider     = google-beta
  display_name = var.service_name
  api_key_id   = google_apikeys_key.sfkit.uid
  depends_on   = [google_firebase_project.firebase]
}

data "google_firebase_web_app_config" "firebase" {
  provider   = google-beta
  web_app_id = google_firebase_web_app.firebase.app_id
}

resource "google_identity_platform_config" "default" {
  authorized_domains = [
    for origin in split(",", var.cors_origins) :
    split(":", split("://", origin)[1])[0]
  ]
  multi_tenant {
    allow_tenants = false
  }
  depends_on = [google_project_service.apis]
}

resource "google_apikeys_key" "sfkit" {
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
    "compute.networks.updatePolicy",
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

    scaling {
      min_instance_count = 1
      max_instance_count = 1
    }

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
        name  = "SERVER_REGION"
        value = var.service_region
      }
      env {
        name  = "SFKIT_CP0_SERVICE_ACCOUNT"
        value = google_service_account.p0_vm.email
      }
      env {
        name  = "SFKIT_CP0_NETWORK_NAME"
        value = google_compute_network.cp0.name
      }
      env {
        name  = "SFKIT_PROXY_ARGS"
        value = var.sfkit_proxy_args
      }
      env {
        name  = "SFKIT_CLI_IMAGE"
        value = var.sfkit_cli_image
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
      env {
        name  = "CLOUDFLARE_TURN_KEY_ID"
        value = var.cloudflare_turn_key_id
      }
      dynamic "env" {
        for_each = var.cloudflare_turn_key_id == "" ? [] : [1]
        content {
          name = "CLOUDFLARE_TURN_KEY_API_TOKEN"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.cloudflare_turn_key_api_token[0].id
              version = "latest"
            }
          }
        }
      }
      env {
        name = "SENDGRID_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.sendgrid_api_key.id
            version = "latest"
          }
        }
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

# SendGrid API Key

resource "google_secret_manager_secret" "sendgrid_api_key" {
  secret_id = "sendgrid_api_key"

  replication {
    user_managed {
      replicas {
        location = var.service_region
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "cloud_run_sendgrid_api_key" {
  secret_id = google_secret_manager_secret.sendgrid_api_key.id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.sa_member
}

# Cloudflare TURN Key

resource "google_secret_manager_secret" "cloudflare_turn_key_api_token" {
  count     = var.cloudflare_turn_key_id == "" ? 0 : 1
  secret_id = "cloudflare_turn_key_api_token"

  replication {
    user_managed {
      replicas {
        location = var.service_region
      }
    }
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_iam_member" "cloud_run_turn_key_api_token" {
  count     = var.cloudflare_turn_key_id == "" ? 0 : 1
  secret_id = google_secret_manager_secret.cloudflare_turn_key_api_token[0].id
  role      = "roles/secretmanager.secretAccessor"
  member    = local.sa_member
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

resource "google_firebaserules_release" "firestore" {
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

# CP0 static VPC + Cloud NAT

locals {
  cp0_net = "sfkit-cp0"
}

resource "google_compute_network" "cp0" {
  name                    = local.cp0_net
  auto_create_subnetworks = false
  depends_on              = [google_project_service.apis]
}

resource "google_compute_subnetwork" "cp0" {
  name          = "${local.cp0_net}-subnet0"
  network       = google_compute_network.cp0.id
  region        = var.service_region
  ip_cidr_range = "10.0.0.0/24"

  log_config {
    aggregation_interval = var.vpc_flow_logs_interval
    flow_sampling        = var.vpc_flow_logs_sampling
    metadata             = "EXCLUDE_ALL_METADATA"
  }
}

resource "google_compute_router" "cp0" {
  name    = "${local.cp0_net}-router"
  network = google_compute_network.cp0.id
  region  = var.service_region
}

resource "google_compute_router_nat" "cp0" {
  name                                = "${local.cp0_net}-nat"
  router                              = google_compute_router.cp0.name
  region                              = var.service_region
  nat_ip_allocate_option              = "AUTO_ONLY"
  source_subnetwork_ip_ranges_to_nat  = "LIST_OF_SUBNETWORKS"
  enable_endpoint_independent_mapping = true
  subnetwork {
    name                    = google_compute_subnetwork.cp0.id
    source_ip_ranges_to_nat = ["ALL_IP_RANGES"]
  }
}
