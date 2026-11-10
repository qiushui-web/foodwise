package org.foodwise;

import org.foodwise.controller.PageController;
import org.foodwise.controller.SpaRoutes;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletResponse;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/** 软 404：不存在的单页路径必须返回 404，而不是笼统的 200。 */
class SpaRoutesTests {

    @Test
    void knownRoutesReturn200() {
        PageController controller = new PageController();
        for (String route : new String[]{"dashboard", "", "evidence", "insights/realtime", "operations/feedback"}) {
            MockHttpServletResponse response = new MockHttpServletResponse();
            controller.vueApp(route, response);
            assertEquals(200, response.getStatus(), "已知路径不应 404：" + route);
        }
    }

    @Test
    void unknownRouteReturns404() {
        MockHttpServletResponse response = new MockHttpServletResponse();
        new PageController().vueApp("no-such-page", response);
        assertEquals(404, response.getStatus());
    }

    @Test
    void trailingSlashAndLeadingSlashAreNormalised() {
        assertTrue(SpaRoutes.isKnown("/evidence/"));
        assertTrue(SpaRoutes.isKnown("evidence"));
        assertFalse(SpaRoutes.isKnown("evidence/extra"));
    }
}