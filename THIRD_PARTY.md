# Licensing and attribution

The original QML integration, Python adapter/installer/tests and thin C++ picker wrapper are released under the existing [MIT license](LICENSE), copyright 2026 DMS AirDrop contributors. The public source inventory contains no vendored DMS, Omdrop, OWL, Qt or KDE implementation, compiled library, font or icon asset. This project was developed with AI assistance.

The release review inspected imports, build links, source headers and file contents, and checked for substantial exact source runs against the installed DMS/Omdrop trees. No copied implementation requiring a different project license was identified. Runtime integration and test stubs describe upstream APIs; tests can link/copy installed DMS components into ignored local fixtures. Those upstream components are not included in Git or release assets. Existing MIT licensing is retained; dependency licenses are not replaced by it.

| Dependency | Interaction | Upstream license/reference |
| --- | --- | --- |
| DankMaterialShell / Avenge Media contributors | QML plugin base types, widgets, theme and toast services imported at runtime | [MIT](https://github.com/AvengeMedia/DankMaterialShell/blob/master/LICENSE) |
| Quickshell contributors | QML runtime and Process API | [LGPL-3.0](https://github.com/quickshell-mirror/quickshell/blob/master/LICENSE) |
| Omdrop / Brent Kearney and contributors | Separate CLI process, status/operation protocol | [MIT](https://github.com/brentkearney/omdrop-plugin/blob/main/LICENSE) |
| omdrop-awdl contributors | Separate optional radio programs; not bundled | [GPL-2.0-only](https://github.com/brentkearney/omdrop-awdl/blob/main/LICENSE) |
| omdrop-owl, SEEMOO OWL and contributors | Separate radio stack; not bundled | [Package provenance](https://github.com/t4t5/omdrop-owl/blob/main/PKGBUILD): GPL-3.0-or-later OWL/patches, GPL-2.0-only separate AWDL tools, ISC radiotap parser |
| Qt contributors | QML modules and dynamically linked Qt6 Widgets in locally built helper | [Qt licensing](https://www.qt.io/licensing/open-source-lgpl-obligations); relevant modules offer LGPL/GPL/commercial terms |
| KDE contributors | Dynamically linked KIOFileWidgets/IconThemes; installed Breeze style/icons and thumbnail plugins | [KIO](https://invent.kde.org/frameworks/kio), [KIconThemes](https://invent.kde.org/frameworks/kiconthemes); individual library/asset licenses apply |

The native wrapper uses KDE's maintained KFileWidget through public APIs. KDE handles browsing, previews and selection; those implementations are not claimed as this project's work. The source release has no prebuilt helper. If you redistribute a compiled helper or dependency assets, review and satisfy their applicable license obligations separately, including notices/source and library replacement requirements where applicable.

AirDrop is a trademark of Apple Inc. All names are used descriptively. This is an independent DMS integration, not an official Apple product and not endorsed by Apple, KDE, DMS or the upstream backend maintainers.
