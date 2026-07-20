import fcntl
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from relay import update_support


class UpdateSupportTest(unittest.TestCase):
    def make_local_checkout(self, root: Path, version: str = "0.7.0") -> tuple[Path, Path]:
        repo = root / "repo"
        home = root / "home"
        repo.mkdir()
        home.mkdir()
        (repo / "relay").mkdir()
        (repo / "relay" / "herdr-mobile-relay-service.sh").write_text("#!/bin/sh\n")
        (repo / "herdr-plugin.toml").write_text(f'version = "{version}"\n')
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "tests@example.test"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Tests"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "commit.gpgsign", "false"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "remote", "add", "origin", update_support.UPSTREAM_GIT_URL],
            check=True,
        )
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "fixture"], check=True)
        service = home / ".config/systemd/user/herdr-mobile-relay.service"
        service.parent.mkdir(parents=True)
        service.write_text(
            f"WorkingDirectory={repo}\n"
            f"ExecStart={repo}/relay/herdr-mobile-relay-service.sh\n"
        )
        return repo, home

    def test_semver_and_manifest_versions_are_strict(self):
        self.assertEqual(update_support.semver("1.2.3"), (1, 2, 3))
        self.assertIsNone(update_support.semver("1.2"))
        self.assertIsNone(update_support.semver("01.2.3"))
        self.assertEqual(update_support.manifest_version('name = "relay"\nversion = "2.0.1"\n'), "2.0.1")
        with self.assertRaises(ValueError):
            update_support.manifest_version('version = "latest"\n')

    def test_local_checkout_reports_only_newer_releases_as_installable(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo, home = self.make_local_checkout(root)
            runtime = root / "runtime"

            available = update_support.check_for_update(
                repo,
                runtime,
                "herdr",
                now=123,
                remote_release=("a" * 40, "0.8.0"),
                home=home,
                system="Linux",
            )
            current = update_support.check_for_update(
                repo,
                runtime,
                "herdr",
                now=124,
                remote_release=("b" * 40, "0.7.0"),
                home=home,
                system="Linux",
            )

        self.assertEqual(available["state"], "available")
        self.assertTrue(available["can_install"])
        self.assertEqual(available["mode"], "local")
        self.assertEqual(available["target_revision"], "a" * 40)
        self.assertEqual(current["state"], "current")
        self.assertFalse(current["can_install"])
        self.assertEqual(current["available_version"], "")
        self.assertEqual(current["upstream_version"], "0.7.0")
        self.assertEqual(current["upstream_revision"], "b" * 40)

    def test_dirty_local_checkout_blocks_an_available_update(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo, home = self.make_local_checkout(root)
            (repo / "local-change.txt").write_text("keep me\n")

            status = update_support.check_for_update(
                repo,
                root / "runtime",
                "herdr",
                remote_release=("c" * 40, "0.8.0"),
                home=home,
                system="Linux",
            )

        self.assertEqual(status["state"], "blocked")
        self.assertFalse(status["can_install"])
        self.assertIn("local changes", status["reason"])

    def test_managed_plugin_is_recognized_from_the_herdr_registry(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo, home = self.make_local_checkout(root)
            herdr = root / "herdr"
            herdr.write_text("#!/bin/sh\n")
            herdr.chmod(0o700)
            registry = home / ".config/herdr/plugins.json"
            registry.parent.mkdir(parents=True, exist_ok=True)
            registry.write_text(json.dumps([{
                "plugin_id": update_support.PLUGIN_ID,
                "plugin_root": str(repo),
                "source": {
                    "kind": "github",
                    "owner": "0cv",
                    "repo": "herdr-mobile-relay",
                },
            }]))

            eligibility = update_support.inspect_installation(
                repo,
                str(herdr),
                home=home,
                system="Linux",
            )

        self.assertEqual(eligibility, {"can_install": True, "mode": "managed", "reason": ""})

    def test_update_job_verifies_restart_before_marking_success(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = root / "runtime"
            runtime.mkdir()
            job_path = runtime / "job.json"
            job_path.write_text(json.dumps({
                "repo_root": str(root / "repo"),
                "runtime_dir": str(runtime),
                "herdr_bin": "herdr",
                "relay_env": "",
                "home": str(root),
                "system": "Linux",
                "mode": "local",
                "previous_version": "0.7.0",
                "previous_revision": "a" * 40,
                "target_version": "0.8.0",
                "target_revision": "b" * 40,
                "checked_at": 123,
            }))
            calls: list[str] = []
            with (
                patch.object(update_support, "_install_local", side_effect=lambda *_: calls.append("install")),
                patch.object(update_support, "_verify_target", side_effect=lambda *_: calls.append("target")),
                patch.object(update_support, "_install_service", side_effect=lambda *_: calls.append("service")),
                patch.object(update_support, "_verify_running_health", side_effect=lambda *_: calls.append("health")),
            ):
                result = update_support.run_update_job(job_path)
            state = json.loads(update_support.state_file(runtime).read_text())

        self.assertEqual(result, 0)
        self.assertEqual(calls, ["install", "target", "service", "health"])
        self.assertEqual(state["state"], "succeeded")
        self.assertEqual(state["current_version"], "0.8.0")
        self.assertFalse(job_path.exists())

    def test_failed_update_rolls_back_and_records_the_outcome(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            runtime = root / "runtime"
            runtime.mkdir()
            job_path = runtime / "job.json"
            job_path.write_text(json.dumps({
                "repo_root": str(root / "repo"),
                "runtime_dir": str(runtime),
                "herdr_bin": "herdr",
                "relay_env": "",
                "home": str(root),
                "system": "Linux",
                "mode": "local",
                "previous_version": "0.7.0",
                "previous_revision": "a" * 40,
                "target_version": "0.8.0",
                "target_revision": "b" * 40,
                "checked_at": 123,
            }))
            rollback = Mock()
            with (
                patch.object(update_support, "_install_local", side_effect=RuntimeError("install broke")),
                patch.object(update_support, "_rollback", rollback),
            ):
                result = update_support.run_update_job(job_path)
            state = json.loads(update_support.state_file(runtime).read_text())

        self.assertEqual(result, 1)
        rollback.assert_called_once()
        self.assertEqual(state["state"], "rolled_back")
        self.assertIn("install broke", state["error"])

    def test_update_job_lock_prevents_overlapping_installers(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime = Path(temp_dir)
            job_path = runtime / "job.json"
            job_path.write_text(json.dumps({"runtime_dir": str(runtime)}))
            with (runtime / update_support.UPDATE_LOCK_NAME).open("w") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = update_support.run_update_job(job_path)

        self.assertEqual(result, 3)
        self.assertFalse(job_path.exists())

    def test_linux_update_launches_in_a_separate_systemd_unit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo, home = self.make_local_checkout(root)
            runtime = root / "runtime"
            completed = subprocess.CompletedProcess([], 0, "", "")
            with (
                patch.object(update_support.shutil, "which", return_value="/usr/bin/systemd-run"),
                patch.object(update_support, "run_command", return_value=completed) as run,
            ):
                label = update_support.launch_update_job(
                    repo,
                    runtime,
                    "herdr",
                    "",
                    {
                        "mode": "local",
                        "current_version": "0.7.0",
                        "available_version": "0.8.0",
                        "target_revision": "d" * 40,
                        "checked_at": 123,
                    },
                    python="/usr/bin/python3",
                    home=home,
                    system="Linux",
                )

            command = run.call_args.args[0]

        self.assertTrue(label.startswith("herdr-mobile-relay-update-"))
        self.assertEqual(command[:3], ["/usr/bin/systemd-run", "--user", "--collect"])
        self.assertIn("--run-job", command)

    def test_app_deploy_config_requires_one_exact_https_origin_and_local_node_tools(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            node_dir = root / "bin"
            node_dir.mkdir()
            node = node_dir / "node"
            npx = node_dir / "npx"
            node.write_text("")
            npx.write_text("")
            config = update_support.app_deploy_config(environ={
                "HERDR_APP_DEPLOY_ORIGIN": "https://App.Example.test/",
                "HERDR_CLOUDFLARE_PAGES_PROJECT": "herdr-app",
                "HERDR_CLOUDFLARE_PAGES_BRANCH": "main",
                "HERDR_APP_DEPLOY_NPX": str(npx),
                "HERDR_APP_DEPLOY_NODE_DIR": str(node_dir),
            })

        self.assertTrue(config["configured"])
        self.assertEqual(config["origin"], "https://app.example.test")

    def test_app_deploy_job_validates_deploys_and_verifies_the_public_origin(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo, _home = self.make_local_checkout(root, version="0.8.0")
            web = repo / "web"
            web.mkdir()
            (web / "version.json").write_text('{"version":"0.8.0","assets":68}\n')
            subprocess.run(["git", "-C", str(repo), "add", "web"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "commit", "-q", "-m", "release bundle"],
                check=True,
            )
            node_dir = root / "bin"
            node_dir.mkdir()
            node = node_dir / "node"
            npx = node_dir / "npx"
            node.write_text("")
            npx.write_text("")
            relay_env = root / "relay.env"
            relay_env.write_text(
                "HERDR_APP_DEPLOY_ORIGIN='https://app.example.test'\n"
                "HERDR_CLOUDFLARE_PAGES_PROJECT='herdr-app'\n"
                "HERDR_CLOUDFLARE_PAGES_BRANCH='main'\n"
                f"HERDR_APP_DEPLOY_NPX='{npx}'\n"
                f"HERDR_APP_DEPLOY_NODE_DIR='{node_dir}'\n"
            )
            revision = update_support.git_output(repo, "rev-parse", "HEAD")
            runtime = root / "runtime"
            runtime.mkdir()
            job_path = runtime / "app-job.json"
            job_path.write_text(json.dumps({
                "repo_root": str(repo),
                "runtime_dir": str(runtime),
                "relay_env": str(relay_env),
                "home": str(root),
                "system": "Linux",
                "origin": "https://app.example.test",
                "project": "herdr-app",
                "target_version": "0.8.0",
                "target_revision": revision,
                "checked_at": 123,
            }))
            completed = subprocess.CompletedProcess([], 0, "ok", "")
            real_run_command = update_support.run_command
            commands: list[list[str]] = []

            def run_command(argv, **kwargs):
                commands.append(argv)
                if argv[0] == "git":
                    return real_run_command(argv, **kwargs)
                return completed

            with (
                patch.object(update_support, "run_command", side_effect=run_command),
                patch.object(update_support, "_verify_deployed_app") as verify,
            ):
                result = update_support.run_app_deploy_job(job_path)
            state = json.loads(update_support.app_deploy_state_file(runtime).read_text())
            deploy_command = commands[-1]

        self.assertEqual(result, 0, state)
        self.assertEqual(state["state"], "succeeded")
        self.assertIn("wrangler@4.112.0", deploy_command)
        self.assertIn("--branch", deploy_command)
        self.assertIn("main", deploy_command)
        verify.assert_called_once_with("https://app.example.test", "0.8.0")
        self.assertFalse(job_path.exists())

    def test_app_deploy_launch_rejects_an_origin_other_than_the_configured_one(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo, home = self.make_local_checkout(root, version="0.8.0")
            web = repo / "web"
            web.mkdir()
            (web / "version.json").write_text('{"version":"0.8.0","assets":68}\n')
            node_dir = root / "bin"
            node_dir.mkdir()
            (node_dir / "node").write_text("")
            (node_dir / "npx").write_text("")
            relay_env = root / "relay.env"
            relay_env.write_text(
                "HERDR_APP_DEPLOY_ORIGIN='https://app.example.test'\n"
                "HERDR_CLOUDFLARE_PAGES_PROJECT='herdr-app'\n"
                f"HERDR_APP_DEPLOY_NPX='{node_dir / 'npx'}'\n"
                f"HERDR_APP_DEPLOY_NODE_DIR='{node_dir}'\n"
            )
            revision = update_support.git_output(repo, "rev-parse", "HEAD")

            with self.assertRaisesRegex(RuntimeError, "not authorized"):
                update_support.launch_app_deploy_job(
                    repo,
                    root / "runtime",
                    str(relay_env),
                    "0.8.0",
                    revision,
                    "https://other.example.test",
                    home=home,
                    system="Linux",
                )

    def test_initial_configured_deploy_uses_the_exact_committed_release(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo, _home = self.make_local_checkout(root, version="0.8.0")
            web = repo / "web"
            web.mkdir()
            (web / "version.json").write_text('{"version":"0.8.0","assets":68}\n')
            subprocess.run(["git", "-C", str(repo), "add", "web"], check=True)
            subprocess.run(
                ["git", "-C", str(repo), "commit", "-q", "-m", "release bundle"],
                check=True,
            )
            node_dir = root / "bin"
            node_dir.mkdir()
            (node_dir / "node").write_text("")
            (node_dir / "npx").write_text("")
            relay_env = root / "config" / "relay.env"
            relay_env.parent.mkdir()
            relay_env.write_text(
                "HERDR_APP_DEPLOY_ORIGIN='https://app.example.test'\n"
                "HERDR_CLOUDFLARE_PAGES_PROJECT='herdr-app'\n"
                f"HERDR_APP_DEPLOY_NPX='{node_dir / 'npx'}'\n"
                f"HERDR_APP_DEPLOY_NODE_DIR='{node_dir}'\n"
            )
            revision = update_support.git_output(repo, "rev-parse", "HEAD")

            with patch.object(update_support, "run_app_deploy_job", return_value=0) as run:
                result = update_support.deploy_configured_app_now(repo, str(relay_env))
            job_path = run.call_args.args[0]
            job = json.loads(job_path.read_text())

        self.assertEqual(result, 0)
        self.assertEqual(job["target_version"], "0.8.0")
        self.assertEqual(job["origin"], "https://app.example.test")
        self.assertEqual(job["target_revision"], revision)

    def test_app_deploy_launch_rejects_uncommitted_release_assets(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            repo, home = self.make_local_checkout(root, version="0.8.0")
            web = repo / "web"
            web.mkdir()
            (web / "version.json").write_text('{"version":"0.8.0","assets":68}\n')
            node_dir = root / "bin"
            node_dir.mkdir()
            (node_dir / "node").write_text("")
            (node_dir / "npx").write_text("")
            relay_env = root / "relay.env"
            relay_env.write_text(
                "HERDR_APP_DEPLOY_ORIGIN='https://app.example.test'\n"
                "HERDR_CLOUDFLARE_PAGES_PROJECT='herdr-app'\n"
                f"HERDR_APP_DEPLOY_NPX='{node_dir / 'npx'}'\n"
                f"HERDR_APP_DEPLOY_NODE_DIR='{node_dir}'\n"
            )
            revision = update_support.git_output(repo, "rev-parse", "HEAD")

            with self.assertRaisesRegex(RuntimeError, "uncommitted bundle changes"):
                update_support.launch_app_deploy_job(
                    repo,
                    root / "runtime",
                    str(relay_env),
                    "0.8.0",
                    revision,
                    "https://app.example.test",
                    home=home,
                    system="Linux",
                )


if __name__ == "__main__":
    unittest.main()
