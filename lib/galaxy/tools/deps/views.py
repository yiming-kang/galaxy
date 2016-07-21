from galaxy.exceptions import (
    RequestParameterMissingException,
    NotImplemented
)


class DependencyResolversView(object):
    """ Provide a RESTfulish/JSONy interface to a galaxy.tools.deps.DependencyResolver
    object. This can be adapted by the Galaxy web framework or other web apps.
    """

    def __init__(self, app):
        self._app = app

    def index(self):
        return map(lambda r: r.to_dict(), self._dependency_resolvers)

    def show(self, index):
        return self._dependency_resolver(index).to_dict()

    def reload(self):
        self.toolbox.reload_dependency_manager()

    def manager_requirements(self):
        requirements = []
        for index, resolver in enumerate(self._dependency_resolvers):
            if not hasattr(resolver, "list_dependencies"):
                continue
            for requirement in resolver.list_dependencies():
                requirements.append({"index": index, "requirement": requirement.to_dict()})
        return requirements

    def resolver_requirements(self, index):
        requirements = []
        resolver = self._dependency_resolver(index)
        if not hasattr(resolver, "list_dependencies"):
            raise NotImplemented()
        for requirement in resolver.list_dependencies():
            requirements.append(requirement.to_dict())
        return requirements

    def manager_dependency(self, **kwds):
        return self._dependency(**kwds)

    def resolver_dependency(self, index, **kwds):
        return self._dependency(**kwds)

    def install_dependency(self, index=None, **payload):
        """
        Installs dependency using highest priority resolver that supports dependency installation
        (Currently only the conda resolver supports this). If index is given, attempt
        installation directly using the corresponding resolver.
        Returns True on success, False on failure.
        payload is dictionary that must container name, version and type,
        e.g. {'name': 'numpy', version='1.9.1', type='package'}
        """
        if index:
            return self._install_dependency(index, **payload)
        else:
            for index in self.installable_resolvers:
                success = self._install_dependency(index, **payload)
                if success:
                    return success
            return False

    def _install_dependency(self, index, **payload):
        """
        Resolver install dependency should return True when installation succeeds,
        False if not successful
        """
        resolver = self._dependency_resolver(index)
        if not hasattr(resolver, "install_dependency"):
            raise NotImplemented()

        name, version, type, extra_kwds = self._parse_dependency_info(payload)
        return resolver.install_dependency(
            name=name,
            version=version,
            type=type,
            **extra_kwds
        )

    def _dependency(self, index=None, **kwds):
        if index is not None:
            index = int(index)

        name, version, type, extra_kwds = self._parse_dependency_info(kwds)
        resolve_kwds = dict(
            job_directory=None,
            index=index,
            **extra_kwds
        )
        dependency = self._dependency_manager.find_dep(
            name, version=version, type=type, **resolve_kwds
        )
        return dependency.to_dict()

    def _parse_dependency_info(self, kwds):
        extra_kwds = kwds.copy()
        name = extra_kwds.pop("name", None)
        if name is None:
            raise RequestParameterMissingException("Missing 'name' parameter required for resolution.")
        version = extra_kwds.pop("version", None)
        type = extra_kwds.pop("type", "package")
        return name, version, type, extra_kwds

    def _dependency_resolver(self, index):
        index = int(index)
        return self._dependency_resolvers[index]

    @property
    def _dependency_manager(self):
        return self._app.toolbox.dependency_manager

    @property
    def _dependency_resolvers(self):
        dependency_manager = self._dependency_manager
        dependency_resolvers = dependency_manager.dependency_resolvers
        return dependency_resolvers

    @property
    def installable_resolvers(self):
        """
        List index for all resolvers that have the 'install_dependency' attribute
        """
        return [index for index, resolver in enumerate(self._dependency_resolvers) if hasattr(resolver, "install_dependency")]

    def get_requirements_status(self, requested_requirements):
        result = []
        for req in requested_requirements:
            installed_requirement = self.requirement_installed(req)
            if not installed_requirement:
                req['status'] = "not installed"
                req['exact'] = "NA"
                req['resolver_type'] = None
                result.append(req)
            else:
                result.append(installed_requirement)
        return result

    def requirement_installed(self, requirement):
        installed_requirements = self.manager_requirements()
        for ireq in installed_requirements:
            if requirement['name'] == ireq['requirement']['name']:
                requirement['resolver_type'] = self._dependency_resolvers[ireq['index']].resolver_type
                versionless = self._dependency_resolvers[ireq['index']].versionless
                if (requirement['version'] == ireq['requirement']['version'] and requirement['version'] and not versionless) or (versionless and not ireq['requirement']['version']):
                    requirement['status'] = "installed"
                    requirement['exact'] = not versionless
                    return requirement
        return None
