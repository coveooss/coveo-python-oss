from coveo_settings.settings import BoolSetting

CI_MODE = BoolSetting("stew.ci.mode", fallback=False)
DRY_RUN = BoolSetting("stew.dry.run", fallback=False)
VERBOSE = BoolSetting("stew.verbose", fallback=False)
