<template>
    <button v-if="RECORD_DATA && RECORD_DATA.id" class="btn btn-link p-2"
            :disabled="loading" @click.prevent.stop="run">
        Primerjaj dele stavb z EV
    </button>
</template>
<script>
export default {
    name: 'PrimerjavaPripisaEv',
    data() { return { loading: false } },
    methods: {
        async run() {
            if (this.loading) return
            this.loading = true
            try {
                const response = await this.$store.dispatch('GenericApi/post', {
                    url: '/xhr/workflows/ComparePripisEvWorkflow',
                    payload: {
                        execute_async: true,
                        workflow_payload: { id_rel_vm_pd: this.RECORD_DATA.id }
                    },
                    options: { headers: { 'x-requested-with': 'XMLHttpRequest', 'Content-Type': 'application/json' } }
                })
                if (response?.status && !String(response.status).startsWith('2')) {
                    throw new Error('Primerjave ni bilo mogoče zagnati.')
                }
            } catch (error) {
                await this.$store.dispatch('AppState/showErrorMessage', {
                    text: error?.message || 'Primerjave ni bilo mogoče zagnati.'
                })
            } finally {
                this.loading = false
            }
        }
    }
}
</script>
