use std::sync::Arc;

use tokio::task::JoinHandle;
use zenoh::{Result, Session as ZSession, config::Locator};
use zenoh_plugin_storage_manager::StoragesPlugin;
use zenoh_plugin_trait::PluginsManager;

pub use zenoh::{Config, config::ZenohId};

use crate::discovery::Discovery;

pub mod discovery;
pub mod swarm;

pub fn is_valid_zid(identity: &str) -> bool {
    let mut iter = identity.chars();
    iter.next()
        .is_some_and(|c| ('1'..='9').contains(&c) || ('a'..='f').contains(&c))
        && iter.all(|c| ('0'..='9').contains(&c) || ('a'..='f').contains(&c))
        && identity.len() <= 32
}

pub fn cfg(identity: &str, listen_port: u16) -> Result<zenoh::Config> {
    assert!(is_valid_zid(identity));
    assert!(identity.len() <= 32);
    let mut cfg = zenoh::Config::default();
    // todo: cleanup
    cfg.insert_json5("id", &format!("\"{identity}\""))?;
    cfg.insert_json5("mode", "\"router\"")?;
    cfg.insert_json5("listen/endpoints", &format!("[\"tcp/[::]:{listen_port}\"]"))?;
    cfg.insert_json5("scouting/multicast/enabled", "false")?;
    cfg.insert_json5("scouting/multicast/autoconnect", "[]")?;
    cfg.insert_json5("scouting/gossip/multihop", "true")?;
    cfg.insert_json5("adminspace/enabled", "true")?;
    //cfg.insert_json5("transport/link/tx/batch_size", "9216")?;
    cfg.insert_json5("transport/link/rx/buffer_size", "16777216")?;
    //cfg.insert_json5("timestamping/enabled", "true")?;
    cfg.insert_json5("plugins/storage_manager/__required__", "true")?;
    cfg.insert_json5(
        "plugins/storage_manager/storages/mem1",
        r#"{
            key_expr: "storage/mem1/**",
            strip_prefix: "storage/mem1",
            volume: "memory",
            replication: {
                interval: 2,
            }
        }"#,
    )?;
    Ok(cfg)
}

pub async fn open(
    cfg: zenoh::Config,
    namespace: &str,
    listen_port: u16,
    discovery_service_port: u16,
) -> Result<Session> {
    let namespace: [u8; 8] = {
        blake3::hash(namespace.as_bytes()).as_bytes()[..8]
            .try_into()
            .expect("8 is equal to 8")
    };
    let mut plugins = PluginsManager::static_plugins_only();
    plugins.declare_static_plugin::<StoragesPlugin, _>("storage_manager", true);
    let mut runtime = zenoh::internal::runtime::RuntimeBuilder::new(cfg)
        .plugins_manager(plugins)
        .build()
        .await?;
    let z = zenoh::session::init(runtime.clone().into()).await?;
    runtime.start().await?;
    let listen_port = if listen_port == 0 {
        z.info()
            .locators()
            .await
            .iter()
            .find_map(port_from_locator)
            .ok_or_else(|| {
                std::io::Error::new(
                    std::io::ErrorKind::AddrNotAvailable,
                    "Zenoh did not report its dynamically assigned TCP listener port",
                )
            })?
    } else {
        listen_port
    };
    let mut discovery =
        Discovery::new(z.zid(), namespace, listen_port, discovery_service_port).await?;
    let _jh = Arc::new(AbortOnDrop(tokio::task::spawn(async move {
        loop {
            let Ok(discovered) = discovery.next().await.inspect_err(|e| {
                log::warn!("discovery error {e}");
            }) else {
                continue;
            };

            if discovered.zid > runtime.zid() {
                log::debug!("not connecting to peer with greater zid");
                continue;
            }

            let Ok(locator) =
                Locator::new("tcp", discovered.addr.to_string(), "").inspect_err(|e| {
                    log::warn!("failed to parse locator from addr: {e}");
                })
            else {
                continue;
            };

            runtime
                .connect_peer(&discovered.zid.into(), &[locator])
                .await;
        }
    })));
    Ok(Session { z, _jh })
}

fn port_from_locator(locator: &Locator) -> Option<u16> {
    let address = locator.as_str().strip_prefix("tcp/")?;
    let (_, port) = address.rsplit_once(':')?;
    port.parse().ok()
}

struct AbortOnDrop(JoinHandle<()>);
impl Drop for AbortOnDrop {
    fn drop(&mut self) {
        self.0.abort();
    }
}

#[derive(Clone)]
pub struct Session {
    pub z: ZSession,
    _jh: Arc<AbortOnDrop>,
}

#[cfg(test)]
mod tests {
    use super::port_from_locator;
    use zenoh::config::Locator;

    #[test]
    fn reads_dynamic_tcp_port_from_ipv6_locator() {
        let locator = Locator::new("tcp", "[::]:49152", "").unwrap();
        assert_eq!(port_from_locator(&locator), Some(49152));
    }

    #[test]
    fn ignores_non_tcp_or_malformed_locators() {
        let udp = Locator::new("udp", "127.0.0.1:49152", "").unwrap();
        let malformed = Locator::new("tcp", "not-a-socket", "").unwrap();
        assert_eq!(port_from_locator(&udp), None);
        assert_eq!(port_from_locator(&malformed), None);
    }

    #[test]
    fn config_accepts_an_ephemeral_listener_port() {
        assert!(super::cfg("11111111111111111111111111111111", 0).is_ok());
    }

    // Nix builds deny sockets; CI runs this integration test outside the sandbox.
    #[cfg_attr(
        feature = "nix-sandbox",
        ignore = "TCP sockets are unavailable in Nix builds"
    )]
    #[tokio::test(flavor = "multi_thread")]
    async fn dynamic_listener_port_is_used_for_discovery() {
        let config = super::cfg("11111111111111111111111111111111", 0).unwrap();
        let session = super::open(config, "dynamic-port-test", 0, 0)
            .await
            .unwrap();
        let listening_port = session
            .z
            .info()
            .locators()
            .await
            .iter()
            .find_map(port_from_locator)
            .unwrap();
        assert_ne!(listening_port, 0);
        drop(session);
    }
}
