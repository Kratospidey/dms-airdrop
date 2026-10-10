// Synthetic pixel-delta input for the offscreen DMS scrolling regression test.
#include <QCoreApplication>
#include <QQuickItem>
#include <QQuickWindow>
#include <QWheelEvent>
#include <QPointingDevice>
#include <QQmlExtensionPlugin>
#include <qqml.h>

class UiInput : public QObject {
    Q_OBJECT
public:
    using QObject::QObject;
    Q_INVOKABLE bool touchpad(QObject *target, int delta) {
        auto *item = qobject_cast<QQuickItem *>(target);
        if (!item || !item->window()) return false;
        const QPointF pos = item->mapToScene(QPointF(item->width() / 2, item->height() / 2));
        const QPointF global = item->window()->mapToGlobal(pos.toPoint());
        static const QPointingDevice pad("Test touchpad", 42, QInputDevice::DeviceType::TouchPad,
            QPointingDevice::PointerType::Finger,
            QInputDevice::Capability::Position | QInputDevice::Capability::PixelScroll | QInputDevice::Capability::Scroll,
            2, 0);
        QWheelEvent event(pos, global, QPoint(0, delta), QPoint(), Qt::NoButton,
                          Qt::NoModifier, Qt::ScrollUpdate, false, Qt::MouseEventSynthesizedByApplication, &pad);
        QCoreApplication::sendEvent(item->window(), &event);
        return event.isAccepted();
    }
};
class UiInputPlugin : public QQmlExtensionPlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID QQmlExtensionInterface_iid)
public:
    void registerTypes(const char *uri) override { qmlRegisterType<UiInput>(uri, 1, 0, "UiInput"); }
};
#include "ui_input.moc"
