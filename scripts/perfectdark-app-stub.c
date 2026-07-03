#include <errno.h>
#include <libgen.h>
#include <limits.h>
#include <mach-o/dyld.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static int get_repo_root(char *repo_root, size_t repo_root_size)
{
	char exec_path[PATH_MAX];
	char resolved_path[PATH_MAX];
	char scratch[PATH_MAX];
	uint32_t exec_path_size = sizeof(exec_path);
	char *dir_path;

	if (_NSGetExecutablePath(exec_path, &exec_path_size) != 0) {
		return -1;
	}

	if (realpath(exec_path, resolved_path) == NULL) {
		return -1;
	}

	strncpy(scratch, resolved_path, sizeof(scratch) - 1);
	scratch[sizeof(scratch) - 1] = '\0';

	dir_path = dirname(scratch); /* MacOS */
	dir_path = dirname(dir_path); /* Contents */
	dir_path = dirname(dir_path); /* PerfectDark.app */
	dir_path = dirname(dir_path); /* repo root */

	if (snprintf(repo_root, repo_root_size, "%s", dir_path) >= (int)repo_root_size) {
		errno = ENAMETOOLONG;
		return -1;
	}

	return 0;
}

int main(int argc, char **argv)
{
	char repo_root[PATH_MAX];
	char launcher_path[PATH_MAX];
	char **child_argv;
	int i;

	if (get_repo_root(repo_root, sizeof(repo_root)) != 0) {
		perror("perfectdark-launcher: resolve repo root");
		return 1;
	}

	if (snprintf(launcher_path, sizeof(launcher_path), "%s/scripts/launch-perfect-dark-aio.sh", repo_root) >= (int)sizeof(launcher_path)) {
		fprintf(stderr, "perfectdark-launcher: launcher path too long\n");
		return 1;
	}

	if (access(launcher_path, R_OK) != 0) {
		perror("perfectdark-launcher: missing launch script");
		return 1;
	}

	if (setenv("PD_REPO_ROOT", repo_root, 1) != 0) {
		perror("perfectdark-launcher: setenv");
		return 1;
	}

	child_argv = calloc((size_t)argc + 2, sizeof(char *));
	if (child_argv == NULL) {
		perror("perfectdark-launcher: calloc");
		return 1;
	}

	child_argv[0] = "/bin/bash";
	child_argv[1] = launcher_path;

	for (i = 1; i < argc; i++) {
		child_argv[i + 1] = argv[i];
	}

	child_argv[argc + 1] = NULL;
	execv(child_argv[0], child_argv);
	perror("perfectdark-launcher: execv");
	return 1;
}
