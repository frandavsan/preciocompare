import { BarChart3, Table2, PieChart, TrendingUp, Star, Settings, Terminal } from "lucide-react";
import { NavLink } from "@/components/NavLink";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarHeader,
  SidebarFooter,
  useSidebar,
} from "@/components/ui/sidebar";

const navItems = [
  { title: "Dashboard", url: "/", icon: BarChart3 },
  { title: "Comparar", url: "/compare", icon: Table2 },
  { title: "Distribución", url: "/distribution", icon: PieChart },
  { title: "Historial", url: "/history", icon: TrendingUp },
  { title: "Favoritos", url: "/favorites", icon: Star },
];

export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";

  return (
    <Sidebar collapsible="icon" className="border-r-2 border-border">
      <SidebarHeader className="p-4 border-b-2 border-border">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-sm bg-primary flex items-center justify-center text-primary-foreground font-mono font-semibold text-xs">
            PC
          </div>
          {!collapsed && (
            <div>
              <h1 className="font-bold text-sm text-sidebar-foreground" style={{ fontFamily: "'IBM Plex Serif', Georgia, serif" }}>
                PrecioCompare
              </h1>
              <p className="font-mono text-[10px] text-muted-foreground tracking-wide uppercase">Argentina · AR$</p>
            </div>
          )}
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel className="font-mono text-[10px] uppercase tracking-widest">Navegación</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.title}>
                  <SidebarMenuButton asChild>
                    <NavLink
                      to={item.url}
                      end={item.url === "/"}
                      className="hover:bg-sidebar-accent rounded-sm font-mono text-sm"
                      activeClassName="bg-sidebar-accent text-primary font-medium border-l-2 border-primary"
                    >
                      <item.icon className="mr-2 h-4 w-4" />
                      {!collapsed && <span>{item.title}</span>}
                    </NavLink>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
      </SidebarContent>

      <SidebarFooter className="p-4 border-t-2 border-border">
        <div className="flex items-center gap-2 text-muted-foreground">
          <Terminal className="h-3 w-3" />
          {!collapsed && <span className="font-mono text-[10px] tracking-wide">v1.0.0 · data.mock</span>}
        </div>
      </SidebarFooter>
    </Sidebar>
  );
}
